import os
import cv2
import tempfile
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_path):
    """Aplica overlay e comprime o vídeo mantendo a qualidade e áudio original."""
    
    # Carregar os vídeos com MoviePy para preservação do áudio
    base_clip = VideoFileClip(video_base_path)
    overlay_clip = VideoFileClip(video_overlay_path).resize(base_clip.size)

    # Abrindo com OpenCV para processar os frames
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # Melhor compatibilidade e compressão
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break

        if ret_overlay:
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.05, 0)
        else:
            frame_final = frame_base  # Se o overlay terminar, continua apenas com o vídeo base

        out.write(frame_final)

    cap_base.release()
    cap_overlay.release()
    out.release()

    # Criar um novo vídeo comprimido com áudio original usando MoviePy
    final_clip = VideoFileClip(output_path)
    final_clip = final_clip.set_audio(base_clip.audio)  # Mantém o áudio original

    # Compactação eficiente usando libx265 e bitrate controlado
    final_clip.write_videofile(
        output_path,
        codec="libx265",   # H.265 para melhor compressão
        audio_codec="aac",  # Compressão eficiente de áudio
        bitrate="800k",     # Redução do bitrate para compactação melhor
        preset="slow"       # Melhor equilíbrio entre tempo de processamento e qualidade
    )

@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Salvar os arquivos temporários corretamente
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        overlay_videos(temp_video_base, temp_video_overlay, temp_output_video)

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")
    
    except Exception as e:
        return {"error": str(e)}
    
    finally:
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        if os.path.exists(temp_output_video):
            os.remove(temp_output_video)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
