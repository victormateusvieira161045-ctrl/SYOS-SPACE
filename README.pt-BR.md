# SYOS SPACE — Reconhecimento Facial Dinâmico

**Protótipo acadêmico | Python · Visão Computacional · Interação por Voz**

[English](README.md)

O SYOS SPACE (pasta original `robo_visao2`) é uma aplicação desktop desenvolvida durante estágio de Engenharia da Computação, em 2026, na Universidade CEUMA, São Luís – MA. Integra detecção facial por webcam, reconhecimento de pessoas previamente cadastradas, cadastro orientado por voz e saudações sonoras. Foi concebido como base para futura integração ao Unitree Edu; a versão atual é independente e não controla o robô.

## Funcionalidades

- Interface Tkinter com vídeo OpenCV e detecção de até três rostos pelo MediaPipe Face Mesh.
- Embeddings FaceNet512 via DeepFace, comparados por distância cosseno (limiar configurado: 0,30).
- Caixa verde para desconhecidos e azul com nome para pessoas reconhecidas.
- Diálogo em português iniciado após aproximadamente três segundos de presença de rosto desconhecido.
- Cadastro com cinco capturas orientadas: centro, direita, esquerda, baixo e cima.
- Persistência SQLite de nome, imagem de referência e embedding médio, além de fotos JPEG locais.
- Saudação por voz com intervalo de dez minutos por pessoa; processamento com threads e filas.

## Requisitos e instalação

Ambiente inicial recomendado: Python 3.11 de 64 bits, Windows 10/11, webcam, microfone, alto-falantes e internet. O reconhecimento de fala depende do serviço Google e a primeira execução pode baixar os pesos do modelo. O projeto não exige um robô para funcionar.

Baixe ou clone o repositório, abra o PowerShell na pasta que contém `app.py` e execute:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe app.py
```

O arquivo `requirements.txt` propõe versões de referência compatíveis com a API legada do MediaPipe. Não foi recuperado o ambiente original e as dependências não foram instaladas ou validadas em execução nesta preparação. O DeepFace e o MediaPipe declaram distribuições distintas do OpenCV; ambas foram fixadas na mesma versão para reduzir conflitos. Em caso de falha de importação de `cv2`, recrie o ambiente e revise as dependências. Em Linux, podem ser necessários Tkinter, PortAudio e eSpeak; consulte o README em inglês. Linux e macOS não foram validados.

## Como utilizar

1. Abra a aplicação e permita acesso à webcam e ao microfone.
2. Posicione-se diante da câmera. O rosto ainda não reconhecido recebe o rótulo `DESCONHECIDO`.
3. Quando o sistema perguntar “Quem é você?”, diga “Registrar”.
4. Informe o nome quando solicitado e siga as orientações de cinco poses, mantendo apenas um rosto visível.
5. Após o cadastro, uma nova identificação pode apresentar a moldura azul, o nome e a saudação sonora.
6. Pressione `Q` para encerrar. A tecla `A` apenas exibe uma instrução no terminal.

## Arquivos

- `app.py`: código-fonte original, preservado sem alterações.
- `requirements.txt`: dependências sugeridas para a instalação.
- `README.md`: documentação em inglês.
- `README.pt-BR.md`: documentação em português.
- `.gitignore`: exclusão de dados locais e temporários do controle de versão.

O banco `rostos.db` é criado automaticamente durante a execução. O arquivo original estava vazio e foi omitido da distribuição, assim como a futura pasta `fotos_cadastradas/`.

## Privacidade e limitações

Protótipo acadêmico para demonstrações controladas com participantes informados e consentidos. Não é um sistema de segurança pronto para produção. Armazena imagens e embeddings faciais sem criptografia; não possui autenticação administrativa, prova de vida, validação geométrica de poses ou interface de exclusão de cadastros. A transcrição de voz usa serviço externo. Não compartilhe dados biométricos nem utilize o sistema para identificação oculta ou decisões de segurança. Não há métricas verificadas de precisão ou desempenho. Os PDFs originais foram mantidos fora do pacote compartilhável, por conterem contexto interno e registros fotográficos; só devem ser distribuídos separadamente com autorização.

## Autores

- Victor Mateus Machado Vieira
- Jackson Garcês Damasceno

Engenharia da Computação — Universidade CEUMA, 2026.

## Distribuição

O projeto original não contém licença de software. Nenhuma licença nova foi atribuída. Antes de publicar ou distribuir publicamente, obtenha autorização dos autores e da organização do estágio.
