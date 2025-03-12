Aqui está o passo a passo completo para instalar o FFmpeg dentro de um contêiner:

Entre no contêiner (substitua nome_do_container pelo nome do seu contêiner):

docker exec -it nome_do_container bash

Atualize os pacotes no contêiner:
apt-get update

Instale as dependências necessáriase ffmpeg:
apt-get install -y apt-transport-https software-properties-common && apt-get install -y ffmpeg

Verifique a instalação do FFmpeg:
ffmpeg -version

Esses comandos vão garantir que o FFmpeg seja instalado corretamente dentro do seu contêiner.
