import os
import cv2
import tempfile
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_video_no_audio):
    """Aplica overlay no vídeo base e salva sem áudio."""

    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec MP4V compatível com OpenCV
    out = cv2.VideoWriter(output_video_no_audio, fourcc, fps, (frame_width, frame_height))

    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break

        if ret_overlay:
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)
        else:
            frame_final = frame_base  # Se o overlay acabar, continua apenas com o vídeo base

        out.write(frame_final)  # Salva o frame final no vídeo de saída

    cap_base.release()
    cap_overlay.release()
    out.release()

    if not os.path.exists(output_video_no_audio):
        raise FileNotFoundError(f"Erro ao gerar o vídeo sem áudio: {output_video_no_audio}")


def extract_audio(video_path, output_audio_path):
    """Extrai o áudio do vídeo base usando Pydub."""
    video = VideoFileClip(video_path)
    
    if video.audio:
        audio = video.audio.to_soundarray(fps=44100)
        audio_segment = AudioSegment(
            np.int16(audio * 32767).tobytes(),
            frame_rate=44100,
            sample_width=2,
            channels=2
        )
        audio_segment.export(output_audio_path, format="mp3")
    else:
        raise FileNotFoundError("O vídeo base não possui áudio.")


def merge_audio_video(video_no_audio_path, audio_path, output_final_path):
    """Adiciona o áudio extraído ao vídeo processado."""
    video = VideoFileClip(video_no_audio_path)
    audio = AudioSegment.from_file(audio_path)

    # Converter o áudio para um formato que MoviePy aceite
    temp_audio_path = tempfile.mktemp(suffix=".mp3")
    audio.export(temp_audio_path, format="mp3")

    final_video = video.set_audio(temp_audio_path)
    final_video.write_videofile(output_final_path, codec="libx264", audio_codec="aac")


@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    """Recebe os vídeos e retorna o vídeo final com overlay e áudio original."""
    
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_video_no_audio = tempfile.mktemp(suffix='.mp4')
    temp_audio_extracted = tempfile.mktemp(suffix='.mp3')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Salvar os vídeos recebidos
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        # Aplica o overlay sem modificar o áudio
        overlay_videos(temp_video_base, temp_video_overlay, temp_video_no_audio)

        # Extrai o áudio do vídeo base
        extract_audio(temp_video_base, temp_audio_extracted)

        # Adiciona o áudio extraído ao vídeo final
        merge_audio_video(temp_video_no_audio, temp_audio_extracted, temp_output_video)

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")
    
    except Exception as e:
        return {"error": str(e)}
    
    finally:
        # Remove arquivos temporários
        for file in [temp_video_base, temp_video_overlay, temp_video_no_audio, temp_audio_extracted, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
