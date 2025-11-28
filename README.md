### **Features**

Three modes:

1. **Idle**
    - Served @ http://{localip}:5000 when device is powered on (Fig2)
    - Includes a power button to remotely shut down device (Fig3)
    - Standard layout with status bubble in top right
    - *Buttons to navigate to other modes across the bottom*
2. **Listening**
    - Monitors audio, averaging volume over the last 2 seconds, every 1 second
    - Live audio RMS visible on screen, visualized against threshold (Fig4)
    - When threshold exceeded, sends notification & records 20-second audio
    - *Buttons to navigate to other modes across the bottom*
3. **Streaming Video**
    - Streams video and audio using WebRTC protocol (Fig1)
    - WebRTC takes a while (15-20 seconds) to handshake with device
    - If streaming after audio threshold exceeded, recorded audio plays (Fig5)
    - Recorded audio can be collapsed, collapsed audio does not auto-play
    - *Buttons to navigate to other modes across the bottom*

**Fig0**\
Raspberry Pi Zero 2 device, & baby, in question:
![IMG_7475](https://github.com/user-attachments/assets/77c03ab4-6eee-45a9-8c72-ce7ec483b741)


**Fig1**\
Streaming video:\
![IMG_7476](https://github.com/user-attachments/assets/51666c22-34a2-40eb-9c04-fcf85602bd7d)


**Fig2**\
Idle mode, when device is powered on:\
<img width="250" height="445" alt="IMG_7576" src="https://github.com/user-attachments/assets/a7a0483e-9028-4425-b885-d09315f51f08" />


**Fig3**\
Power off device remotely:\
<img width="250" height="250" alt="IMG_7572" src="https://github.com/user-attachments/assets/87bdd466-3584-4519-847c-8bb30115c020" />


**Fig4**\
Live audio monitoring against field-tested threshold:\
<img width="237" height="422" alt="IMG_7577" src="https://github.com/user-attachments/assets/54bb7061-0ef9-4ac6-81d2-ed8afc3fb2a7" />


**Fig5**\
Recorded above-threshold audio autoplays, while video connects:\
<img width="445" height="250" alt="IMG_7573" src="https://github.com/user-attachments/assets/83f769f2-ef13-4f97-8b2b-8e35cd6c0aaa" />
