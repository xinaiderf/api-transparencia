from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import cv2
import tempfile
import os
import subprocess
import uvicorn

app = FastAPI()

# Função para sobrepor os vídeos
def overlay_videos(video_base_path, video_overlay_path, output_path):
    # Carregar os dois vídeos usando OpenCV
    cap_base = cv2.VideoCapture(video_base_path)
    cap_overlay = cv2.VideoCapture(video_overlay_path)
    
    # Obter informações dos vídeos
    fps = cap_base.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap_base.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap_base.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Criar o writer para salvar o vídeo final
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Usando o codec mp4v
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    while cap_base.isOpened() and cap_overlay.isOpened():
        ret_base, frame_base = cap_base.read()
        ret_overlay, frame_overlay = cap_overlay.read()

        if not ret_base or not ret_overlay:
            break

        # Redimensionar o vídeo sobreposto para o mesmo tamanho do vídeo de fundo
        frame_overlay_resized = cv2.resize(frame_overlay, (frame_width, frame_height))

        # Aplica a transparência (15%) no vídeo sobreposto
        frame_overlay_resized = cv2.addWeighted(frame_base, 1.0, frame_overlay_resized, 0.15, 0)

        # Escreve o frame no arquivo de saída
        out.write(frame_overlay_resized)
    
    # Libera os recursos
    cap_base.release()
    cap_overlay.release()
    out.release()
    print(f"Vídeo final gerado em: {output_path}")

# Função para adicionar o áudio usando ffmpeg
def add_audio_to_video(video_path, audio_path, output_video_path):
    # Usa ffmpeg para adicionar o áudio ao vídeo
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path, '-c:v', 'libx264', '-c:a', 'aac',
        '-strict', 'experimental', '-shortest', '-y', output_video_path
    ]
    subprocess.run(command)

# Endereço da API
@app.post("/overlay/")
async def overlay_api(video_base: UploadFile = File(...), video_overlay: UploadFile = File(...)):
    # Salva os arquivos binários recebidos do n8n
    temp_video_base = tempfile.mktemp(suffix='.mp4')
    temp_video_overlay = tempfile.mktemp(suffix='.mp4')

    # Escrever o conteúdo binário nos arquivos temporários
    with open(temp_video_base, "wb") as f:
        f.write(await video_base.read())

    with open(temp_video_overlay, "wb") as f:
        f.write(await video_overlay.read())

    # Caminho temporário para o vídeo de saída
    temp_output_video = tempfile.mktemp(suffix='.mp4')
    temp_audio_path = tempfile.mktemp(suffix='.mp3')

    try:
        # Primeiro, sobrepõe os vídeos
        overlay_videos(temp_video_base, temp_video_overlay, temp_output_video)

        # Extrai o áudio do vídeo base (usando ffmpeg)
        audio_command = [
            'ffmpeg', '-i', temp_video_base, '-vn', '-acodec', 'mp3', temp_audio_path
        ]
        subprocess.run(audio_command)

        # Adiciona o áudio extraído ao vídeo final
        add_audio_to_video(temp_output_video, temp_audio_path, temp_output_video)

        # Envia o arquivo gerado como resposta
        return FileResponse(temp_output_video, media_type='video/mp4', filename='video_final.mp4')
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Remove os arquivos temporários
        os.remove(temp_video_base)
        os.remove(temp_video_overlay)
        os.remove(temp_audio_path)

# Rodando o servidor
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8010)
