instalar ffmpeg no terminal da vps (sudo apt install ffmpeg)

Entre no conteiner
docker exec -it nome_do_container bash
No terminal do contêiner, crie um link simbólico para o FFmpeg:
ln -s /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg

isso vai fazer com que use o ffmpeg da vps no conteiner
