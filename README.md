GUIMAN Video downloader 🚀

Shorts Creator Ultimate é uma aplicação em Python + Flask que permite baixar vídeos do YouTube, gerar shorts automáticos com transcrição, análise de viralidade e legendas destacáveis. Os arquivos gerados são mantidos no servidor por 24 horas e removidos automaticamente para liberar espaço.

🔹 Funcionalidades

Baixar vídeos do YouTube usando yt-dlp.

Gerar shorts automáticos com duração configurável (padrão ≤50s).

Gerar transcrição segmentada de cada short usando faster-whisper.

Detectar emoções no vídeo e analisar sentimento do áudio/texto.

Exibir legendas interativas arrastáveis e destacáveis.

Limpeza automática de arquivos antigos após 24h.

Interface web moderna com logs em tempo real.

🛠 Tecnologias

Python 3.10+

Flask

yt-dlp

faster-whisper

imageio-ffmpeg

librosa

transformers

DeepFace

HTML/CSS/JS para frontend

LocalStorage no navegador para persistência temporária do usuário

⚡ Instalação
1. Clone o repositório
git clone https://github.com/mafaldo-dev/guiman-downloader.git <br/>
cd guiman-downloader

2. Crie um ambiente virtual (recomendado)
python -m venv venv <br />
source venv/bin/activate      # Linux/macOS <br/>
venv\Scripts\activate         # Windows

3. Instale as dependências
pip install -r requirements.txt


⚠️ Dependências críticas: yt-dlp, faster-whisper, imageio-ffmpeg, librosa, transformers, deepface

⚙️ Configuração

Certifique-se de ter FFmpeg instalado no sistema.

O projeto cria automaticamente as pastas:

downloads → vídeos baixados

shorts → shorts gerados

Se quiser usar cookies do YouTube para vídeos privados:

Crie um arquivo cookies.txt na raiz do projeto.

🚀 Como rodar
python app.py


Acesse a aplicação via navegador em: http://localhost:5000

Cole a URL do YouTube, clique em Processar Vídeo, e veja os shorts gerados com legendas interativas.

🧹 Limpeza automática

Todos os arquivos nas pastas downloads e shorts são removidos automaticamente após 24h.

A verificação ocorre a cada 1 hora (configurável no código).

💻 Estrutura do Projeto
shorts-creator-ultimate/
│
├─ app.py                  # Backend Flask + lógica de shorts
├─ templates/
│   └─ index.html          # Frontend HTML/JS
├─ downloads/              # Vídeos baixados
├─ shorts/                 # Shorts e thumbnails gerados
├─ requirements.txt        # Dependências Python
└─ README.md               # Este arquivo

🛠 Como contribuir

Fork este repositório.

Crie uma branch para sua feature ou bugfix:

git checkout -b minha-feature


Faça suas alterações e commit:

git commit -m "Descrição da mudança"


Push para sua branch:

git push origin minha-feature


Abra um Pull Request aqui no repositório original.

📌 Observações

Recomendado usar Python 3.10+ para compatibilidade com faster-whisper e transformers.

O projeto não inclui suporte a servidores remotos por padrão; para deploy, recomenda-se usar Render, Heroku ou VPS.

Vídeos de longa duração podem demorar para processar dependendo da capacidade da máquina.
