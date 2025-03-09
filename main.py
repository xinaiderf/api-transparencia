import os
import cv2
import numpy as np
import tempfile
import subprocess
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()


def apply_overlay(video_base_path, video_overlay_path, output_video_path_no_audio):
    """Aplica um overlay com 5% de transparência no vídeo base e mantém o áudio original."""

    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    # Verifica se os vídeos foram abertos corretamente
    if not cap_base.isOpened():
        raise RuntimeError(f"Erro ao abrir o vídeo base: {video_base_path}")
    if not cap_overlay.isOpened():
        raise RuntimeError(f"Erro ao abrir o vídeo overlay: {video_overlay_path}")

    # Propriedades do vídeo base
    fps = int(cap_base.get(cv2.CAP_PROP_FPS))
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Criar um vídeo de saída SEM ÁUDIO com as mesmas propriedades do vídeo base
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path_no_audio, fourcc, fps, (frame_width, frame_height))

    while True:
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break  # Se o vídeo base acabou, parar

        if ret_overlay:
            # Redimensionar overlay para o tamanho do vídeo base
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))

            # Aplicar transparência de 5% no overlay
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.05, 0)
        else:
            frame_final = frame_base  # Se o overlay acabar, mantém o vídeo base puro

        out.write(frame_final)  # Escrever no vídeo de saída

    # Fechar os arquivos
    cap_base.release()
    cap_overlay.release()
    out.release()

    # Verificar se o arquivo foi criado corretamente
    if not os.path.exists(output_video_path_no_audio):
        raise FileNotFoundError(f"Erro ao gerar o vídeo final sem áudio: {output_video_path_no_audio}")


def merge_audio(video_base_path, video_no_audio_path, output_final_path):
    """Mantém o áudio original do vídeo base e adiciona ao vídeo processado."""
    
    temp_output = output_final_path.replace(".mp4", "_temp.mp4")

    command = [
        "ffmpeg", "-i", video_no_audio_path, "-i", video_base_path,
        "-c", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-y", temp_output
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.replace(temp_output, output_final_path)


@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    """Recebe dois vídeos e retorna o vídeo final com overlay e áudio original."""

    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_video_no_audio = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Salvar os vídeos temporários
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        # Aplicar overlay sem mexer no áudio
        apply_overlay(temp_video_base, temp_video_overlay, temp_video_no_audio)

        # Manter o áudio original
        merge_audio(temp_video_base, temp_video_no_audio, temp_output_video)

        # Garantir que o arquivo final foi gerado corretamente antes de enviar a resposta
        if not os.path.exists(temp_output_video):
            raise FileNotFoundError("O arquivo final não foi gerado corretamente.")

        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")

    except Exception as e:
        return {"error": str(e)}

    finally:
        # Remover arquivos temporários após processamento
        for file in [temp_video_base, temp_video_overlay, temp_video_no_audio, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
