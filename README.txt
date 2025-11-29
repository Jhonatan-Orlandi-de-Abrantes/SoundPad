📌 Como configurar o SoundPad pela primeira vez

O SoundPad precisa de um driver virtual para misturar sua voz + o áudio dos sons em um único microfone.
Se você já instalou o aplicativo usando PySoundPad Installer, ignore esta seção.

1️⃣ Instale o VB-Audio Cable

Download oficial: https://vb-audio.com/Cable/

- Execute o instalador

- Reinicie o PC

- Após instalado, aparecerá um dispositivo chamado: CABLE Input / CABLE Output

2️⃣ Instale o VoiceMeeter Banana

- Download: https://vb-audio.com/Voicemeeter/banana.htm

- Instale e reinicie o computador

- Abra o VoiceMeeter Banana

3️⃣ Configure o áudio no Windows

- Abra: Configurações → Sistema → Som

- E defina:
         Função         |         Dispositivo
Dispositivo de entrada     CABLE In (VB-Audio Virtual)

4️⃣ Configure no VoiceMeeter

- No VoiceMeeter Banana:
     Stereo Inputs     |         Configuração
Stereo Input 1	            (Seu microfone)
Stereo Input 2              "CABLE Input" ou "CABLE Output"

5️⃣ Configure o SoundPad

- No programa:

- Abra Configurações

- Selecione o dispositivo: CABLE Output

Teste:
- Abra Discord / Zoom / OBS / etc.
- Vá em Configurar entrada de microfone → selecione: VoiceMeeter Out B1 (VB-Audio Voicemeeter VAIO)

Agora:
- Sua voz e os sons do SoundPad vão ser transmitidos como único input de microfone.

!!! Observações: !!!
- Se ao pressionar o botão "" o programa travar e fechar sozinho, é porque o "ffmpeg" não foi encontrado, como resolver:
     1. Instale o "ffmpeg" no link: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
     2. Após extrair, abra e execute na pasta: ...\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe
     4. Copie o caminho da pasta "bin", como: ...\ffmpeg-8.0.1-essentials_build\bin\
     5. Abra o Painel de Controle, e pesquise por "Variáveis de Ambiente".
     6. Procure pela variável Path, clique em Editar e adicione o caminho que você copiou.
     7. Confirme tudo, reinicie o programa e teste.