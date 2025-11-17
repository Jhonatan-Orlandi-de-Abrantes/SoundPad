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
           Função                   |              	     Dispositivo
Dispositivo de entrada padrão	                    VoiceMeeter Output
Dispositivo de entrada secundário (se existir)      Cable Output
Dispositivo de saída	                            Seu headset ou alto-falante

4️⃣ Configure no VoiceMeeter

- No VoiceMeeter Banana:
        Campo	   |         Configuração
Hardware Input 1	    Seu microfone real
Virtual Input	        Mantém padrão
B1 / B2	                Ative apenas B1 para enviar ao microfone
Patch	                Roteie "CABLE Input" → "VoiceMeeter Output"

5️⃣ Configure o SoundPad

- No programa:

- Abra Configurações

- Selecione o dispositivo: CABLE Output
(Isso enviará o áudio para o microfone virtual)

Teste! :
- Abra Discord / Zoom / OBS / etc.
- Vá em Configurar entrada de microfone → selecione: VoiceMeeter Output

Agora: 
- Sua voz e os sons do SoundPad vão ser transmitidos como único input de microfone.