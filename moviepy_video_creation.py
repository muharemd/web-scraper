import os
from moviepy import ImageClip, AudioFileClip, vfx

IMAGE_PATH = "static/images/out.jpg"
AUDIO_PATH = "static/audios/bihac_vijesti.mp3"
OUTPUT_PATH = "static/videos/bihac_danas_short.mp4"

os.makedirs("static/videos", exist_ok=True)

def create_bihac_video():
    try:
        print("Učitavam resurse...")
        audio = AudioFileClip(AUDIO_PATH)
        
        # Dodajemo .convert("RGB") da osiguramo da slika nije u nekom čudnom formatu
        # Force-ujemo rezoluciju na standardni format (1280x720)
        clip = (ImageClip(IMAGE_PATH)
                .with_duration(audio.duration)
                .with_effects([vfx.Resize(height=720)])
                .with_position("center"))
        
        video = clip.with_audio(audio)
        
        print(f"Renderujem video ({audio.duration:.2f}s)...")
        
        video.write_videofile(
            OUTPUT_PATH, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            # pixel_format je ključan za Windows kompatibilnost
            ffmpeg_params=["-pix_fmt", "yuv420p"], 
            preset="ultrafast",
            threads=1
        )
        print(f"\nUspjeh! Video je spreman: {OUTPUT_PATH}")

    except Exception as e:
        print(f"\nGreška: {e}")

if __name__ == "__main__":
    create_bihac_video()
