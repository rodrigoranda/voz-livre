# Janela "Sobre" do Voz Livre
import os, sys, webbrowser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import customtkinter as ctk
import voz_livre as app

ROXO, ROXO_HOVER = "#7c5cff", "#6a4be6"
CARD, CHIP, CINZA, CLARO = "#1b1b22", "#2a2a35", "#8a8a99", "#c9c9d6"
F = "Segoe UI"
REPO = "https://github.com/rodrigoranda/voz-livre"

TEXTO_APP = (
    "Ditado por voz com IA para Windows. Segure uma tecla, fale e solte: "
    "o texto aparece onde estiver o cursor. Também lê textos em voz alta (traduzindo "
    "para o português) e reescreve textos com um comando de voz.\n\n"
    "Grátis, de código aberto e pode funcionar 100% offline, no seu próprio computador."
)
TEXTO_NORONHA = (
    "O Voz Livre nasceu em Fernando de Noronha, um arquipélago vulcânico no meio do "
    "Atlântico, a cerca de 545 km de Recife. São 21 ilhas e ilhotas, a maior parte "
    "protegida pelo Parque Nacional Marinho e reconhecida pela UNESCO como Patrimônio "
    "Natural da Humanidade. É a terra da Baía do Sancho, várias vezes eleita a praia "
    "mais bonita do mundo, e dos golfinhos-rotadores da Baía dos Golfinhos.\n\n"
    "Em uma ilha, a internet nem sempre colabora. Por isso o app foi pensado para "
    "funcionar também sem conexão. Ele foi feito por um morador da ilha há mais de 40 "
    "anos, que sempre trabalhou com tecnologia, para facilitar o dia a dia de quem atende "
    "clientes, turistas e vizinhos pelo WhatsApp."
)


def main():
    ctk.set_appearance_mode("dark")
    janela = ctk.CTk(fg_color="#121217")
    janela.title("Sobre o Voz Livre")
    janela.geometry("480x720")
    janela.resizable(False, True)
    try:
        janela.iconbitmap(app.ICO)
    except Exception:
        pass
    janela.attributes("-topmost", True)
    janela.after(400, lambda: janela.attributes("-topmost", False))

    topo = ctk.CTkFrame(janela, fg_color="transparent")
    topo.pack(fill="x", padx=28, pady=(26, 4))
    ctk.CTkLabel(topo, text="Voz Livre", font=(F + " Semibold", 30)).pack(anchor="w")
    ctk.CTkLabel(topo, text=f"Versão {app.VERSAO}  ·  Fale em vez de digitar. Ouça em vez de ler.",
                 font=(F, 13), text_color=CINZA).pack(anchor="w")

    corpo = ctk.CTkScrollableFrame(janela, fg_color="transparent", scrollbar_button_color=CHIP)
    corpo.pack(fill="both", expand=True, padx=6, pady=(8, 0))

    def card(titulo, texto):
        f = ctk.CTkFrame(corpo, corner_radius=16, fg_color=CARD)
        f.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(f, text=titulo, font=(F + " Semibold", 15)).pack(anchor="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(f, text=texto, font=(F, 12.5), text_color=CLARO, wraplength=390,
                     justify="left").pack(anchor="w", padx=18, pady=(0, 16))
        return f

    card("O que é", TEXTO_APP)
    card("Feito em Fernando de Noronha", TEXTO_NORONHA)
    card("Créditos", "Usa Whisper (OpenAI), faster-whisper (SYSTRAN), Groq, vozes do Microsoft Edge "
                     "(edge-tts), CustomTkinter, pystray, keyboard, sounddevice e outras bibliotecas "
                     "de código aberto. A lista completa, com as licenças, está no README do projeto.")
    card("Licença", "MIT: use, modifique e distribua à vontade, inclusive em projetos comerciais. "
                    "Só mantenha o aviso de copyright.\n\nProjeto independente, sem ligação com "
                    "Wispr, OpenAI, Groq ou Microsoft.")

    rodape = ctk.CTkFrame(janela, fg_color="transparent")
    rodape.pack(fill="x", padx=20, pady=14)
    ctk.CTkButton(rodape, text="Ver no GitHub", height=42, corner_radius=12, font=(F + " Semibold", 14),
                  fg_color=ROXO, hover_color=ROXO_HOVER, command=lambda: webbrowser.open(REPO)).pack(side="left", expand=True, fill="x", padx=(0, 6))
    ctk.CTkButton(rodape, text="Fechar", height=42, corner_radius=12, font=(F, 14), fg_color=CHIP,
                  hover_color="#383846", command=janela.destroy).pack(side="left", expand=True, fill="x", padx=(6, 0))
    ctk.CTkLabel(janela, text="© 2026 Rodrigo Morais · Fernando de Noronha, PE · Brasil",
                 font=(F, 11), text_color=CINZA).pack(pady=(0, 12))
    janela.mainloop()


if __name__ == "__main__":
    main()
