import os
from openai import OpenAI

# ------------------------------------------------------------------
# Load the OpenAI API key from the config file (.openai_config),
# falling back to the environment variable if the file is absent.
# File format (shell-sourceable):  export OPENAI_API_KEY="sk-..."
# NEVER hardcode secrets in source.
# ------------------------------------------------------------------
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".openai_config")


def load_api_key():
    # 1) Try the config file
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                # Skip comments and blank lines
                if not line or line.startswith("#"):
                    continue
                # Handle both "export OPENAI_API_KEY=..." and "OPENAI_API_KEY=..."
                if line.startswith("export "):
                    line = line[len("export "):]
                if line.startswith("OPENAI_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value

    # 2) Fall back to environment variable
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key

    raise RuntimeError(
        f"OPENAI_API_KEY not found. Set it in {CONFIG_FILE} "
        '(e.g. export OPENAI_API_KEY="sk-...") or as an environment variable.'
    )


client = OpenAI(api_key=load_api_key())


def testiraj_bihac_glas():
    # Tekst tipične vijesti sa tvog portala
    naslov = "Velika pobjeda Jedinstva pod Borićima!"
    vijest = "Danas je pred punim tribinama stadiona pod Borićima, nogometni klub Jedinstvo savladao gostujuću ekipu rezultatom tri naprema nula. Navijači su proslavili pobjedu uz pjesmu i vatromet."

    print("--- Započinjem generisanje glasa ---")

    try:
        # Generisanje audia
        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",  # Možeš probati: 'onyx' (muški), 'nova' (ženski), 'shimmer'
            input=f"{naslov} {vijest}"
        )

        # Snimanje u lokalni fajl
        filename = "test_bihac_danas.mp3"
        response.stream_to_file(filename)

        print(f"--- USPJEH! ---")
        print(f"Fajl je sačuvan kao: {os.path.abspath(filename)}")
        print("Sada ga možeš preuzeti i poslušati.")

    except Exception as e:
        print(f"Došlo je do greške: {e}")


if __name__ == "__main__":
    testiraj_bihac_glas()

