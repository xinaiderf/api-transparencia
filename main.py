import os
import cv2
import tempfile
import numpy as np
import ffmpeg
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()

def overlay_videos(video_base_path, video_overlay_path, output_video_no_audio):
    """Aplica overlay no vídeo base e salva sem áudio."""

    # Carregar os vídeos com OpenCV
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)

    # Obtém as propriedades do vídeo base
    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Configura o VideoWriter usando o codec MP4V (compatível com OpenCV)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec MP4V para evitar erro
    out = cv2.VideoWriter(output_video_no_audio, fourcc, fps, (frame_width, frame_height))

    # Processar os frames e aplicar o overlay
    while cap_base.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base:
            break  # Se o vídeo base acabar, interrompe o loop

        if ret_overlay:
            # Redimensiona o overlay para o tamanho do vídeo base
            frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))
            frame_final = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)
        else:
            frame_final = frame_base  # Se o overlay acabar, continua apenas com o vídeo base

        out.write(frame_final)  # Salva o frame final no vídeo de saída

    # Libera os vídeos e finaliza o processamento
    cap_base.release()
    cap_overlay.release()
    out.release()

    # Verifica se o arquivo foi gerado corretamente
    if not os.path.exists(output_video_no_audio):
        raise FileNotFoundError(f"Erro ao gerar o vídeo sem áudio: {output_video_no_audio}")


def add_original_audio(video_base_path, video_no_audio_path, output_final_path):
    """Adiciona o áudio original do vídeo base ao vídeo processado, sem reprocessar."""
    
    # Garante que o vídeo sem áudio existe antes de tentar adicionar o áudio
    if not os.path.exists(video_no_audio_path):
        raise FileNotFoundError(f"Vídeo sem áudio não encontrado: {video_no_audio_path}")

    # Mescla o vídeo com o áudio original usando ffmpeg-python
    ffmpeg.input(video_no_audio_path).output(
        output_final_path, 
        vcodec="copy",  # Mantém o vídeo sem reprocessar
        acodec="copy",  # Mantém o áudio original
        map="0:v",  # Usa o vídeo do arquivo sem áudio
        map="1:a"   # Usa o áudio do vídeo base
    ).run(overwrite_output=True)


@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    """Recebe os vídeos e retorna o vídeo final com overlay e áudio original."""
    
    # Criando arquivos temporários
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')
    temp_video_no_audio = tempfile.mktemp(suffix='.mp4')
    temp_output_video = tempfile.mktemp(suffix='.mp4')

    try:
        # Salvar os vídeos enviados para arquivos temporários
        with open(temp_video_base, "wb") as f:
            f.write(await video_base.read())

        with open(temp_video_overlay, "wb") as f:
            f.write(await video_overlay.read())

        # Aplica o overlay sem modificar o áudio
        overlay_videos(temp_video_base, temp_video_overlay, temp_video_no_audio)

        # Adiciona o áudio original sem reprocessamento
        add_original_audio(temp_video_base, temp_video_no_audio, temp_output_video)

        # Retorna o vídeo final ao usuário
        return FileResponse(temp_output_video, media_type='video/mp4', filename="output.mp4")
    
    except Exception as e:
        return {"error": str(e)}
    
    finally:
        # Remove os arquivos temporários com segurança
        for file in [temp_video_base, temp_video_overlay, temp_video_no_audio, temp_output_video]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
