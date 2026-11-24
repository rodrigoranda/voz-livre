# Tela de configuracoes do Voz Livre (visual moderno com customtkinter)
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import customtkinter as ctk
import keyboard
import voz_livre as ditado

ROXO, ROXO_HOVER = "#7c5cff", "#6a4be6"
CARD, CHIP, CINZA = "#1b1b22", "#2a2a35", "#8a8a99"
F = "Segoe UI"


def main():
    ctk.set_appearance_mode("dark")
    c = ditado.ler_cfg()
    app = ctk.CTk(fg_color="#121217")
    app.title("Voz Livre")
    app.geometry("500x760")
    app.resizable(False, True)
    try:
        app.iconbitmap(ditado.ICO)
    except Exception:
        pass
    app.attributes("-topmost", True)
    app.after(400, lambda: app.attributes("-topmost", False))

    # Cabecalho
    topo = ctk.CTkFrame(app, fg_color="transparent")
    topo.pack(fill="x", padx=28, pady=(24, 4))
    linha_topo = ctk.CTkFrame(topo, fg_color="transparent")
    linha_topo.pack(fill="x")
    ctk.CTkLabel(linha_topo, text="Voz Livre", font=(F + " Semibold", 30)).pack(side="left")
    ctk.CTkButton(linha_topo, text="ⓘ  Sobre", width=90, height=30, corner_radius=8, fg_color=CHIP,
                  hover_color="#383846", command=ditado.abrir_sobre).pack(side="right")
    ctk.CTkLabel(topo, text="Fale em vez de digitar. Ouça em vez de ler.",
                 font=(F, 13), text_color=CINZA).pack(anchor="w")

    # Rodape fixo (botao salvar)
    rodape = ctk.CTkFrame(app, fg_color="transparent")
    rodape.pack(side="bottom", fill="x", padx=20, pady=(6, 14))
    aviso = ctk.CTkLabel(rodape, text="", font=(F, 12), text_color="#3ddc97")

    corpo = ctk.CTkScrollableFrame(app, fg_color="transparent", scrollbar_button_color=CHIP)
    corpo.pack(fill="both", expand=True, padx=6)

    def card(titulo, sub):
        f = ctk.CTkFrame(corpo, corner_radius=16, fg_color=CARD)
        f.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(f, text=titulo, font=(F + " Semibold", 15)).pack(anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(f, text=sub, font=(F, 12), text_color=CINZA, wraplength=400, justify="left").pack(anchor="w", padx=18)
        return f

    def campo_tecla(f, chave, sugestoes=None, rotulo=None):
        if rotulo:
            ctk.CTkLabel(f, text=rotulo, font=(F, 12), text_color=CINZA).pack(anchor="w", padx=18, pady=(8, 0))
        var = ctk.StringVar(value=c[chave])
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(6, 4 if sugestoes else 14))
        ctk.CTkLabel(row, textvariable=var, font=("Consolas", 14), fg_color=CHIP, corner_radius=8,
                     width=210, height=36).pack(side="left")

        def capturar():
            btn.configure(text="Aperte agora…", fg_color="#e5484d", hover_color="#e5484d")
            def t():
                hk = keyboard.read_hotkey(suppress=False)
                app.after(0, lambda: (var.set(hk), btn.configure(text="Trocar", fg_color=ROXO, hover_color=ROXO_HOVER)))
            threading.Thread(target=t, daemon=True).start()
        btn = ctk.CTkButton(row, text="Trocar", width=120, height=36, corner_radius=8,
                            fg_color=ROXO, hover_color=ROXO_HOVER, command=capturar)
        btn.pack(side="right")
        if sugestoes:
            m = ctk.CTkOptionMenu(f, values=[n for n, _ in sugestoes], width=210, height=30, corner_radius=8,
                                  fg_color=CHIP, button_color=CHIP, button_hover_color="#383846",
                                  command=lambda n: var.set(dict(sugestoes)[n]))
            m.set("Sugestões de tecla…")
            m.pack(anchor="w", padx=18, pady=(4, 14))
        return var


    # 1. Ditar
    f1 = card("Ditar", "Segure a tecla, fale e solte. O texto aparece onde está o cursor.")
    tecla = campo_tecla(f1, "tecla", ditado.OPCOES)
    sw_enviar = ctk.CTkSwitch(f1, text="Apertar Enter sozinho depois de ditar (envia no WhatsApp)",
                              font=(F, 12), progress_color=ROXO)
    if c.get("enviar_auto"):
        sw_enviar.select()
    sw_enviar.pack(anchor="w", padx=18, pady=(0, 14))

    # 2. Comando com IA
    f2 = card("Comando com IA",
              "Selecione um texto, segure a tecla e diga o que fazer (\"deixa mais formal\", "
              "\"traduz pro inglês\"). Sem nada selecionado, ele escreve um texto novo do zero.")
    tecla_cmd = campo_tecla(f2, "tecla_comando")

    # 3. Motor
    f3 = card("Onde transcrever", "Se um falhar, o outro entra sozinho como reserva.")
    motores = {"Meu PC (rápido, offline)": "pc", "Só nuvem / Groq (0 MB)": "groq"}
    seg = ctk.CTkSegmentedButton(f3, values=list(motores), height=36, corner_radius=8,
                                 selected_color=ROXO, selected_hover_color=ROXO_HOVER,
                                 unselected_color=CHIP, fg_color=CHIP)
    seg.set(next(n for n, v in motores.items() if v == c["motor"]))
    seg.pack(fill="x", padx=18, pady=(10, 4))
    ctk.CTkLabel(f3, text="Modelo no PC (só baixa se escolher \"Meu PC\"):", font=(F, 12),
                 text_color=CINZA).pack(anchor="w", padx=18, pady=(8, 0))
    nomes_mod = {v: n for n, v in ditado.MODELOS}
    mod = ctk.CTkOptionMenu(f3, values=[n for n, _ in ditado.MODELOS], height=34, corner_radius=8,
                            fg_color=CHIP, button_color=CHIP, button_hover_color="#383846")
    mod.set(nomes_mod.get(c["modelo"], ditado.MODELOS[0][0]))
    mod.pack(fill="x", padx=18, pady=(4, 4))
    ctk.CTkLabel(f3, text="Chave da Groq (grátis em console.groq.com):", font=(F, 12),
                 text_color=CINZA).pack(anchor="w", padx=18, pady=(8, 0))
    chave = ctk.CTkEntry(f3, height=36, corner_radius=8, fg_color=CHIP, border_width=0, show="•",
                         placeholder_text="gsk_...")
    if ditado.chave_groq():
        chave.insert(0, ditado.chave_groq())
    chave.pack(fill="x", padx=18, pady=(4, 16))

    # 4. Leitura
    f4 = card("Ler em voz alta", "Selecione um texto e aperte a tecla: traduz e lê em português. "
                                 "Aperte de novo para parar.")
    tecla_ler = campo_tecla(f4, "tecla_ler")
    row = ctk.CTkFrame(f4, fg_color="transparent")
    row.pack(fill="x", padx=18, pady=(0, 16))
    nomes_voz = {v: n for n, v in ditado.VOZES}
    voz = ctk.CTkOptionMenu(row, values=[n for n, _ in ditado.VOZES], width=210, height=36, corner_radius=8,
                            fg_color=CHIP, button_color=CHIP, button_hover_color="#383846")
    voz.set(nomes_voz.get(c["voz"], ditado.VOZES[0][0]))
    voz.pack(side="left")

    def ouvir():
        v = dict(ditado.VOZES)[voz.get()]
        ditado.parar_leitura.clear()
        threading.Thread(target=ditado.falar, args=("Olá! Esta é a minha voz.", v), daemon=True).start()
    ctk.CTkButton(row, text="▶  Ouvir", width=120, height=36, corner_radius=8, fg_color=CHIP,
                  hover_color="#383846", command=ouvir).pack(side="right")

    # 5. Historico e dicionario
    f5 = card("Histórico e dicionário", "Os últimos ditados ficam no menu do ícone (clique para copiar).")
    tecla_colar = campo_tecla(f5, "tecla_colar", rotulo="Colar de novo o último ditado:")
    ctk.CTkButton(f5, text="Editar dicionário de palavras", height=34, corner_radius=8, fg_color=CHIP,
                  hover_color="#383846", command=lambda: os.startfile(ditado.DICIONARIO)).pack(anchor="w", padx=18, pady=(0, 16))

    # 6. Comandos de voz (cola)
    f6 = card("Comandos de voz", "Fale durante o ditado:")
    dicas = ("vírgula · ponto final · dois pontos\n"
             "ponto de interrogação · ponto de exclamação\n"
             "nova linha · novo parágrafo\n"
             "\"... envia mensagem\" no fim  →  aperta Enter\n"
             "\"apaga isso\" sozinho  →  apaga o último ditado")
    ctk.CTkLabel(f6, text=dicas, font=("Consolas", 12), justify="left", text_color="#c9c9d6").pack(anchor="w", padx=18, pady=(6, 16))

    # Pilula flutuante (muda ao vivo)
    fp = card("Pílula flutuante", "Arraste a pílula com o mouse para onde quiser. "
                                  "Os controles abaixo mudam na hora.")

    def ajustar_pilula(**valores):
        atual = ditado.ler_cfg()
        atual.update(valores)
        atual["pilula_mostrar_ate"] = time.time() + 4      # mostra para voce ver a mudanca
        ditado.salvar_cfg(atual)

    def slider(rotulo, chave, minimo, maximo, padrao):
        linha = ctk.CTkFrame(fp, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkLabel(linha, text=rotulo, font=(F, 12), text_color=CINZA, width=110, anchor="w").pack(side="left")
        valor = ctk.CTkLabel(linha, text="", font=(F, 12), width=44)
        valor.pack(side="right")
        s = ctk.CTkSlider(linha, from_=minimo, to=maximo, progress_color=ROXO, button_color=ROXO,
                          button_hover_color=ROXO_HOVER)
        s.set(float(c.get(chave, padrao)) * 100)
        valor.configure(text=f"{int(s.get())}%")

        def mudou(v):
            valor.configure(text=f"{int(v)}%")
            ajustar_pilula(**{chave: round(v / 100, 2)})
        s.configure(command=mudou)
        s.pack(side="left", fill="x", expand=True, padx=8)
    slider("Tamanho", "pilula_escala", 60, 200, 1.0)
    slider("Opacidade", "pilula_opacidade", 30, 100, 0.95)

    botoes = ctk.CTkFrame(fp, fg_color="transparent")
    botoes.pack(fill="x", padx=18, pady=(12, 16))
    ctk.CTkButton(botoes, text="Mostrar para posicionar", height=34, corner_radius=8, fg_color=ROXO,
                  hover_color=ROXO_HOVER, command=ditado.mostrar_pilula_para_posicionar).pack(side="left")
    ctk.CTkButton(botoes, text="Voltar ao padrão", height=34, corner_radius=8, fg_color=CHIP,
                  hover_color="#383846", command=lambda: ajustar_pilula(pilula_x=None, pilula_y=None,
                  pilula_escala=1.0, pilula_opacidade=0.95)).pack(side="right")

    # Sobre voce (contexto para a IA)
    f_sobre = card("Sobre você (opcional)", "Ajuda a IA do Comando a escrever do seu jeito. Ex.: \"técnico de TI, atendo clientes pelo WhatsApp\".")
    sobre = ctk.CTkEntry(f_sobre, height=36, corner_radius=8, fg_color=CHIP, border_width=0,
                         placeholder_text="Quem é você, com o que trabalha...")
    if c.get("sobre_mim"):
        sobre.insert(0, c["sobre_mim"])
    sobre.pack(fill="x", padx=18, pady=(8, 16))

    # 7. Geral
    f7 = ctk.CTkFrame(corpo, corner_radius=16, fg_color=CARD)
    f7.pack(fill="x", padx=10, pady=(10, 6))
    sw = ctk.CTkSwitch(f7, text="Iniciar junto com o Windows", font=(F, 13), progress_color=ROXO)
    if ditado.inicia_com_windows():
        sw.select()
    sw.pack(anchor="w", padx=18, pady=16)

    def salvar():
        # mantem o que a pilula salvou enquanto esta tela estava aberta (posicao, tamanho...)
        c.update({k: v for k, v in ditado.ler_cfg().items() if k.startswith("pilula_")})
        c["tecla"], c["tecla_ler"], c["tecla_colar"], c["tecla_comando"] = \
            tecla.get(), tecla_ler.get(), tecla_colar.get(), tecla_cmd.get()
        c["motor"] = motores[seg.get()]
        c["voz"] = dict(ditado.VOZES)[voz.get()]
        c["enviar_auto"] = bool(sw_enviar.get())
        c["sobre_mim"] = sobre.get().strip()
        c["modelo"] = dict(ditado.MODELOS)[mod.get()]
        k = chave.get().strip()
        if k and k != ditado.chave_groq():
            with open(os.path.join(ditado.BASE, ".env"), "w", encoding="utf-8") as fe:
                fe.write(f"GROQ_API_KEY={k}\n")
        ditado.salvar_cfg(c)
        if bool(sw.get()) != ditado.inicia_com_windows():
            ditado.alternar_iniciar()
        aviso.configure(text="✓  Salvo! Já está valendo.")
        app.after(900, app.destroy)
    ctk.CTkButton(rodape, text="Salvar", height=46, corner_radius=12, font=(F + " Semibold", 15),
                  fg_color=ROXO, hover_color=ROXO_HOVER, command=salvar).pack(fill="x")
    aviso.pack(pady=(4, 0))
    app.mainloop()


if __name__ == "__main__":
    main()
