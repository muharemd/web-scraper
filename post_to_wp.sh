#!/bin/bash
set -euo pipefail
shopt -s nullglob

BASE_DIR="/home/bihac-danas/web-scraper"
CONFIG_FILE="$BASE_DIR/.wp_config"

DRY_RUN="false"
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN="true"
            ;;
        -h|--help)
            echo "Usage: $0 /absolute/path/to/article.json [category_id] [--dry-run]"
            exit 0
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

ARTICLE_JSON="${POSITIONAL_ARGS[0]:-}"
CATEGORY_OVERRIDE="${POSITIONAL_ARGS[1]:-}"
if [ -z "$ARTICLE_JSON" ]; then
    echo "Usage: $0 /absolute/path/to/article.json [category_id] [--dry-run]"
    exit 1
fi

if [ ! -f "$ARTICLE_JSON" ]; then
    echo "ERROR: Article JSON not found: $ARTICLE_JSON"
    exit 1
fi

AUTH=""
WP_STATUS_VALUE="${WP_STATUS:-publish}"
CURL_CONNECT_TIMEOUT="${WP_CURL_CONNECT_TIMEOUT:-10}"
CURL_MAX_TIME="${WP_CURL_MAX_TIME:-30}"

if [ "$DRY_RUN" = "false" ]; then
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "ERROR: Config file not found at $CONFIG_FILE"
        echo "Create it from .wp_config.example and set WordPress credentials."
        exit 1
    fi

    set -a
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
    set +a

    if [ -z "${WP_BASE:-}" ] || [ -z "${WP_USERNAME:-}" ] || [ -z "${WP_APP_PASSWORD:-}" ]; then
        echo "ERROR: Missing WP_BASE, WP_USERNAME, or WP_APP_PASSWORD in $CONFIG_FILE"
        exit 1
    fi

    AUTH="${WP_USERNAME}:${WP_APP_PASSWORD}"
    WP_STATUS_VALUE="${WP_STATUS:-publish}"
    CURL_CONNECT_TIMEOUT="${WP_CURL_CONNECT_TIMEOUT:-10}"
    CURL_MAX_TIME="${WP_CURL_MAX_TIME:-30}"
else
    echo "Running in dry-run mode: WordPress publish and media uploads are skipped."
fi

TITLE=$(jq -r '.title_rewritten // .title // "Bez naslova"' "$ARTICLE_JSON")
CONTENT=$(jq -r '.content // ""' "$ARTICLE_JSON")
SOURCE_URL=$(jq -r '.url // empty' "$ARTICLE_JSON")
CONTENT_COVERAGE_LABEL=$(jq -r '.content_coverage_label // ""' "$ARTICLE_JSON")
CONTENT_TRUNCATED_FLAG=$(jq -r '.content_truncated_for_facebook // false' "$ARTICLE_JSON")
CONTENT_FULL_LENGTH=$(jq -r 'if (.content_full_length | type) == "number" then .content_full_length else 0 end' "$ARTICLE_JSON")
CONTENT_POST_LENGTH=$(jq -r 'if (.content_post_length | type) == "number" then .content_post_length else 0 end' "$ARTICLE_JSON")
IMAGE_URL=$(jq -r '.image_url // empty' "$ARTICLE_JSON")
mapfile -t IMAGE_URLS < <(jq -r '(.image_urls // []) | if type == "array" then .[] else empty end' "$ARTICLE_JSON")
CATEGORY=""
if [ -n "$CATEGORY_OVERRIDE" ]; then
    if [[ "$CATEGORY_OVERRIDE" =~ ^[0-9]+$ ]]; then
        CATEGORY="$CATEGORY_OVERRIDE"
    else
        echo "Warning: invalid category override '$CATEGORY_OVERRIDE', using JSON/default category."
    fi
fi

if [ -z "$CATEGORY" ] || [ "$CATEGORY" = "null" ]; then
    CATEGORY=$(jq -r '.wp_category // empty' "$ARTICLE_JSON")
fi
if [ -z "$CATEGORY" ] || [ "$CATEGORY" = "null" ]; then
    CATEGORY="${WP_DEFAULT_CATEGORY:-}"
fi

if [[ "$CATEGORY" =~ ^[0-9]+$ ]]; then
    echo "Using WordPress category: $CATEGORY"
else
    echo "No numeric WordPress category selected; post will keep WP default behavior."
fi

PARTIAL_CONTENT="false"
case "$CONTENT_COVERAGE_LABEL" in
    likely_partial|possibly_partial|empty)
        PARTIAL_CONTENT="true"
        ;;
esac

if [ "$CONTENT_TRUNCATED_FLAG" = "true" ]; then
    PARTIAL_CONTENT="true"
fi

if [ "$CONTENT_FULL_LENGTH" -gt 0 ] && [ "$CONTENT_POST_LENGTH" -gt 0 ] && [ "$CONTENT_FULL_LENGTH" -gt "$CONTENT_POST_LENGTH" ]; then
    PARTIAL_CONTENT="true"
fi

# Legacy posts may not have metadata; content near the old 900-char cap is likely truncated.
if [ "$PARTIAL_CONTENT" = "false" ] && [ -z "$CONTENT_COVERAGE_LABEL" ] && [ "${#CONTENT}" -ge 960 ]; then
    PARTIAL_CONTENT="true"
fi

if [ -n "$SOURCE_URL" ] && [ "$SOURCE_URL" != "null" ]; then
    ESCAPED_SOURCE_URL=$(jq -rn --arg value "$SOURCE_URL" '$value | @html')
    SOURCE_LINE_EMOJI="🔗 Pročitaj više: $SOURCE_URL"
    SOURCE_LINE_PLAIN="Procitaj vise: $SOURCE_URL"
    SOURCE_LINK_HTML="<a href=\"${ESCAPED_SOURCE_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">${ESCAPED_SOURCE_URL}</a>"
    SOURCE_HTML_LINE_EMOJI="🔗 Pročitaj više: ${SOURCE_LINK_HTML}"
    SOURCE_HTML_LINE_PLAIN="Procitaj vise: ${SOURCE_LINK_HTML}"

    if [[ "$CONTENT" == *"$SOURCE_LINE_EMOJI"* ]]; then
        CONTENT="${CONTENT//$SOURCE_LINE_EMOJI/$SOURCE_HTML_LINE_EMOJI}"
    elif [[ "$CONTENT" == *"$SOURCE_LINE_PLAIN"* ]]; then
        CONTENT="${CONTENT//$SOURCE_LINE_PLAIN/$SOURCE_HTML_LINE_PLAIN}"
    elif [[ "$CONTENT" == *"$SOURCE_URL"* ]]; then
        CONTENT="${CONTENT//$SOURCE_URL/$SOURCE_LINK_HTML}"
    else
        CONTENT="${CONTENT}"$'\n\n'"<p>🔗 Pročitaj više: ${SOURCE_LINK_HTML}</p>"
    fi

    echo "Source link mode: hyperlink."
fi

SOURCE_KEY=$(jq -r '.source // empty' "$ARTICLE_JSON")
ARTICLE_ID=$(jq -r '.id // empty' "$ARTICLE_JSON")
ATTACHMENTS_FOLDER=$(jq -r '.attachments_folder // empty' "$ARTICLE_JSON")

declare -a CANDIDATE_FOLDERS=()
if [ -n "$ATTACHMENTS_FOLDER" ] && [ "$ATTACHMENTS_FOLDER" != "null" ]; then
    CANDIDATE_FOLDERS+=("$ATTACHMENTS_FOLDER")
fi
if [ -n "$SOURCE_KEY" ] && [ -n "$ARTICLE_ID" ]; then
    CANDIDATE_FOLDERS+=("$BASE_DIR/facebook_ready_posts/attachments/$SOURCE_KEY/$ARTICLE_ID")
fi
if [ -n "$ARTICLE_ID" ]; then
    CANDIDATE_FOLDERS+=("$BASE_DIR/facebook_ready_posts/attachments/$ARTICLE_ID")
fi

FOLDER=""
for CANDIDATE in "${CANDIDATE_FOLDERS[@]}"; do
    if [ -d "$CANDIDATE" ]; then
        FOLDER="$CANDIDATE"
        break
    fi
done

IMG_HTML=""
FIRST_ID=""

upload_media_file() {
    local media_file="$1"
    local media_name="$2"
    local media_type="$3"

    local response id url
    response=$(curl -sS -X POST "$WP_BASE/media" \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        -u "$AUTH" \
        -H "Content-Disposition: attachment; filename=$media_name" \
        -H "Content-Type: $media_type" \
        --data-binary "@$media_file")

    id=$(echo "$response" | jq -r '.id // empty')
    url=$(echo "$response" | jq -r '.source_url // empty')

    if [[ "$id" =~ ^[0-9]+$ ]] && [ -n "$url" ]; then
        echo "$id|$url"
        return 0
    fi

    echo ""
    return 1
}

download_remote_file() {
    local remote_url="$1"
    local output_file="$2"

    if curl -fsSL \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        "$remote_url" -o "$output_file"; then
        return 0
    fi

    # Some FB CDN hosts prefer IPv4 when server IPv6 egress is unavailable.
    if curl -4 -fsSL \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        "$remote_url" -o "$output_file"; then
        echo "  Download succeeded with IPv4 fallback."
        return 0
    fi

    return 1
}

append_remote_image_url() {
    local remote_url="$1"
    local label="${2:-remote-image}"
    local temp_image clean_url remote_name ext ctype upload_result id url

    [ -n "$remote_url" ] || return 0

    temp_image="$(mktemp /tmp/wp-image-XXXXXX)"
    clean_url="${remote_url%%\?*}"
    remote_name="$(basename "$clean_url")"
    if [ -z "$remote_name" ] || [ "$remote_name" = "/" ] || [[ "$remote_name" == *":"* ]]; then
        remote_name="${label}.jpg"
    fi

    if download_remote_file "$remote_url" "$temp_image"; then
        ext=$(echo "${remote_name##*.}" | tr '[:upper:]' '[:lower:]')
        ctype=""
        case "$ext" in
            png) ctype="image/png" ;;
            jpg|jpeg) ctype="image/jpeg" ;;
            webp) ctype="image/webp" ;;
            gif) ctype="image/gif" ;;
            avif) ctype="image/avif" ;;
        esac

        if [ -z "$ctype" ] && command -v file >/dev/null 2>&1; then
            ctype=$(file -b --mime-type "$temp_image" 2>/dev/null || true)
        fi
        if [ -z "$ctype" ]; then
            ctype="application/octet-stream"
        fi

        upload_result=$(upload_media_file "$temp_image" "$remote_name" "$ctype" || true)
        id="${upload_result%%|*}"
        url="${upload_result#*|}"

        if [[ "$id" =~ ^[0-9]+$ ]] && [ -n "$url" ] && [ "$url" != "$upload_result" ]; then
            echo "  Uploaded remote image: id=$id"
            if [ -z "$FIRST_ID" ]; then
                FIRST_ID="$id"
            fi
            IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${url}\" /></figure>"
        else
            echo "  Warning: failed to upload remote image to WordPress media."
            IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${remote_url}\" /></figure>"
        fi
    else
        echo "  Warning: could not download remote image: $remote_url"
        IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${remote_url}\" /></figure>"
    fi

    rm -f "$temp_image"
}

if [ "$DRY_RUN" = "true" ]; then
    echo "Dry-run: using JSON image URLs directly (no media upload)."
    if [ ${#IMAGE_URLS[@]} -gt 0 ]; then
        for REMOTE_IMAGE_URL in "${IMAGE_URLS[@]}"; do
            [ -n "$REMOTE_IMAGE_URL" ] || continue
            IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${REMOTE_IMAGE_URL}\" /></figure>"
        done
    elif [ -n "$IMAGE_URL" ] && [ "$IMAGE_URL" != "null" ]; then
        IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${IMAGE_URL}\" /></figure>"
    fi
else
    if [ -n "$FOLDER" ]; then
        echo "Searching images in: $FOLDER"
        FILES=("$FOLDER"/*.jpg "$FOLDER"/*.jpeg "$FOLDER"/*.png "$FOLDER"/*.webp "$FOLDER"/*.gif "$FOLDER"/*.avif)

        for PHOTO in "${FILES[@]}"; do
            [ -f "$PHOTO" ] || continue

            FILENAME=$(basename "$PHOTO")
            EXT=$(echo "${FILENAME##*.}" | tr '[:upper:]' '[:lower:]')
            CTYPE=""
            case "$EXT" in
                png) CTYPE="image/png" ;;
                jpg|jpeg) CTYPE="image/jpeg" ;;
                webp) CTYPE="image/webp" ;;
                gif) CTYPE="image/gif" ;;
                avif) CTYPE="image/avif" ;;
                *) continue ;;
            esac

            echo "Uploading image: $FILENAME"
            UPLOAD_RESULT=$(upload_media_file "$PHOTO" "$FILENAME" "$CTYPE" || true)
            ID="${UPLOAD_RESULT%%|*}"
            URL="${UPLOAD_RESULT#*|}"

            if [[ "$ID" =~ ^[0-9]+$ ]] && [ -n "$URL" ] && [ "$URL" != "$UPLOAD_RESULT" ]; then
                echo "  Uploaded: id=$ID"
                if [ -z "$FIRST_ID" ]; then
                    FIRST_ID="$ID"
                fi
                IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${URL}\" /></figure>"
            else
                echo "  Warning: image upload failed for $FILENAME"
            fi
        done
    else
        echo "No image attachments folder detected for this article."
    fi

    if [ -z "$IMG_HTML" ] && [ ${#IMAGE_URLS[@]} -gt 0 ]; then
        echo "Trying gallery images from image_urls..."
        for REMOTE_IMAGE_URL in "${IMAGE_URLS[@]}"; do
            [ -n "$REMOTE_IMAGE_URL" ] || continue
            append_remote_image_url "$REMOTE_IMAGE_URL" "image-from-json"
        done
    fi

    if [ -z "$IMG_HTML" ] && [ -n "$IMAGE_URL" ] && [ "$IMAGE_URL" != "null" ]; then
        echo "Trying featured image from image_url..."
        append_remote_image_url "$IMAGE_URL" "featured-image"
    fi
fi

FINAL_CONTENT="$CONTENT"
if [ -n "$IMG_HTML" ]; then
    FINAL_CONTENT="${FINAL_CONTENT}"$'\n\n'"${IMG_HTML}"
fi

JSON_DATA=$(jq -n \
    --arg title "$TITLE" \
    --arg content "$FINAL_CONTENT" \
    --arg status "$WP_STATUS_VALUE" \
    '{title: $title, content: $content, status: $status, comment_status: "closed"}')

if [[ "$CATEGORY" =~ ^[0-9]+$ ]]; then
    JSON_DATA=$(echo "$JSON_DATA" | jq --argjson cat "$CATEGORY" '. + {categories: [$cat]}')
fi

if [[ "$FIRST_ID" =~ ^[0-9]+$ ]]; then
    JSON_DATA=$(echo "$JSON_DATA" | jq --argjson featured "$FIRST_ID" '. + {featured_media: $featured}')
fi

if [ "$DRY_RUN" = "true" ]; then
    DRY_RUN_FILE=$(mktemp /tmp/wp-dry-run-XXXXXX.json)
    printf '%s\n' "$JSON_DATA" > "$DRY_RUN_FILE"

    CONTENT_PREVIEW=$(printf '%s' "$FINAL_CONTENT" | tr '\n' ' ' | tr -s ' ' | cut -c1-220)
    echo "Dry run complete. WordPress post was not created."
    echo "Dry-run payload saved to: $DRY_RUN_FILE"
    echo "Preview: $CONTENT_PREVIEW"

    RESULT_JSON=$(jq -cn \
        --arg status "dry-run" \
        --arg payload_file "$DRY_RUN_FILE" \
        --arg title "$TITLE" \
        --arg category "$CATEGORY" \
        '{status: $status, payload_file: $payload_file, title: $title, category: $category}')
    echo "__WP_RESULT__${RESULT_JSON}"
    exit 0
fi

echo "Creating WordPress post..."
RESULT=$(curl -sS -X POST "$WP_BASE/posts" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    --max-time "$CURL_MAX_TIME" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$JSON_DATA")

POST_ID=$(echo "$RESULT" | jq -r '.id // empty')
LINK=$(echo "$RESULT" | jq -r '.link // empty')
ERROR_MSG=$(echo "$RESULT" | jq -r '.message // empty')

if ! [[ "$POST_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: WordPress publish failed."
    if [ -n "$ERROR_MSG" ]; then
        echo "WordPress error: $ERROR_MSG"
    fi
    echo "$RESULT"
    exit 1
fi

echo "Post published successfully."
echo "Post ID: $POST_ID"
echo "URL: $LINK"

RESULT_JSON=$(jq -cn --arg status "success" --arg post_id "$POST_ID" --arg link "$LINK" '{status: $status, post_id: $post_id, link: $link}')
echo "__WP_RESULT__${RESULT_JSON}"

