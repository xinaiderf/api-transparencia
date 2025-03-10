from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip, CompositeVideoClip, AudioFileClip
from PIL import Image
import tempfile
import os
import uvicorn

app = FastAPI()

def overlay_videos_with_audio(video_base_path, video_overlay_path, output_path, transparencia):
    # Carregar os clipes de vídeo usando o MoviePy
    base_clip = VideoFileClip(video_base_path)
    overlay_clip = VideoFileClip(video_overlay_path)
    
    # Ajustar a duração do overlay para ser igual à duração do vídeo base
    overlay_resized = overlay_clip.resize(base_clip.size)
    overlay_resized = overlay_resized.set_duration(base_clip.duration)
    
    # Se necessário, redimensionar a imagem do overlay com o método correto do Pillow
    overlay_resized = overlay_resized.fx(vfx.resize, base_clip.size, resample=Image.Resampling.LANCZOS)
    
    # Combinar os vídeos com transparência (caso necessário)
    video_combined = CompositeVideoClip([base_clip, overlay_resized.set_opacity(transparencia)])
    
    # Caso tenha áudio no vídeo base, podemos adicionar ao vídeo combinado
    if base_clip.audio:
        audio = base_clip.audio
    elif overlay_clip.audio:
        audio = overlay_clip.audio
    else:
        audio = None
    
    # Definir o áudio para o vídeo final, se presente
    if audio:
        video_combined = video_combined.set_audio(audio)
    
    # Escrever o arquivo final
    video_combined.write_videofile(output_path, codec="libx264", audio_codec="aac")

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...), transparencia: float = 0.05):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())
    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())
    
    try:
        overlay_videos_with_audio(temp_video_base, temp_video_overlay, temp_output_video, transparencia)
        return FileResponse(temp_output_video, media_type='video/mp4', filename='output.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
