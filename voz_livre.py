# Voz Livre - ditado por voz para Windows: segure a tecla, fale, solte e o texto aparece onde o cursor estiver.
# Abrir:      pythonw voz_livre.py   (ou o atalho criado pelo instalar.bat)
# Configurar: icone na bandeja (perto do relogio) > "Configurações"
# Licenca MIT - https://github.com/rodrigoranda/voz-livre
import os, sys, json, time, threading, io, wave, logging, subprocess

VERSAO = "1.2.1"
BASE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(BASE, "config.json")
PADRAO = {"tecla": "ctrl+windows", "motor": "pc", "tecla_ler": "ctrl+shift+l", "voz": "pt-BR-FranciscaNeural",
          "tecla_colar": "ctrl+alt+v", "tecla_comando": "f8", "enviar_auto": False,
          "sobre_mim": "", "modelo": "large-v3-turbo"}
MODELOS = [("Completo - melhor qualidade (1,5 GB)", "large-v3-turbo"), ("Leve - mais rápido de baixar (460 MB)", "small")]
VOZES = [("Francisca (feminina)", "pt-BR-FranciscaNeural"), ("Antônio (masculina)", "pt-BR-AntonioNeural"),
         ("Thalita (feminina)", "pt-BR-ThalitaMultilingualNeural")]
OPCOES = [
    ("Ctrl + Win (recomendado)", "ctrl+windows"),
    ("Ctrl direito", "right ctrl"),
    ("Alt direito", "right alt"),
    ("Ctrl + Alt", "ctrl+alt"),
    ("F9", "f9"),
    ("Caps Lock", "caps lock"),
]
logging.basicConfig(filename=os.path.join(BASE, "voz_livre.log"), level=logging.INFO,
                    format="%(asctime)s %(message)s", encoding="utf-8")


def ler_cfg():
    c = dict(PADRAO)
    try:
        with open(CFG, encoding="utf-8") as f:
            c.update(json.load(f))
    except Exception:
        pass
    return c


def salvar_cfg(c):
    # grava num arquivo temporario e troca de uma vez (ninguem le o arquivo pela metade)
    tmp = CFG + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    for _ in range(5):
        try:
            os.replace(tmp, CFG)
            return
        except PermissionError:
            time.sleep(0.05)



# ---------------- Transcricao ----------------
modelo = None
modelo_status = "carregando"


def carregar_modelo():
    global modelo, modelo_status
    cfg = ler_cfg()
    if cfg["motor"] != "pc":
        # so nuvem: nao baixa nem carrega nada pesado
        modelo, modelo_status = None, "desligado"
        return
    nome = cfg.get("modelo", "large-v3-turbo")
    modelo_status = "carregando"
    try:
        from faster_whisper import WhisperModel
        try:
            modelo = WhisperModel(nome, device="cuda", compute_type="float16")
        except Exception as e:
            # sem placa de video: roda no processador (mais lento, mas funciona sem internet)
            logging.warning("Sem GPU (%s); usando o processador", e)
            modelo = WhisperModel(nome, device="cpu", compute_type="int8")
        modelo_status = "pronto"
    except Exception as e:
        logging.exception("Falha ao carregar o modelo local: %s", e)
        modelo_status = "erro"


def chave_groq():
    try:
        for linha in open(os.path.join(BASE, ".env"), encoding="utf-8"):
            if linha.startswith("GROQ_API_KEY="):
                return linha.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


DICIONARIO = os.path.join(BASE, "dicionario.txt")
DICIONARIO_INICIAL = """# Dicionario do Voz Livre
# 1) Palavras soltas: nomes e termos que devem sair escritos certo (uma por linha)
# 2) Correcoes: "como ele escreve errado => como deve ficar"
# Linhas com # sao ignoradas. Salve o arquivo e ja vale (nao precisa reiniciar).
# Dica: selecione uma palavra, segure F8 e diga "adiciona no dicionário".

WhatsApp
Pix
GitHub

zap zap => WhatsApp
git hub => GitHub
"""


def ler_dicionario():
    if not os.path.exists(DICIONARIO):
        open(DICIONARIO, "w", encoding="utf-8").write(DICIONARIO_INICIAL)
    palavras, trocas = [], []
    for linha in open(DICIONARIO, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if "=>" in linha:
            errado, certo = (p.strip() for p in linha.split("=>", 1))
            if errado:
                trocas.append((errado, certo))
        else:
            palavras.append(linha)
    return palavras, trocas


def dica_whisper():
    # frase de contexto: ajuda o Whisper a acertar os nomes do dicionario
    palavras, _ = ler_dicionario()
    return ("Ditado em português do Brasil. Termos: " + ", ".join(palavras) + ".") if palavras else None


def aplicar_trocas(texto):
    import re
    for errado, certo in ler_dicionario()[1]:
        texto = re.sub(r"(?<!\w)" + re.escape(errado) + r"(?!\w)", certo, texto, flags=re.IGNORECASE)
    return texto


def pelo_pc(audio):
    segs, _ = modelo.transcribe(audio, language="pt", beam_size=1, vad_filter=True, initial_prompt=dica_whisper())
    return " ".join(s.text.strip() for s in segs).strip()


def pela_groq(audio):
    import numpy as np, requests
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    w.close()
    r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                      headers={"Authorization": f"Bearer {chave_groq()}"},
                      files={"file": ("fala.wav", buf.getvalue(), "audio/wav")},
                      data={"model": "whisper-large-v3-turbo", "language": "pt", "prompt": dica_whisper() or ""},
                      timeout=30)
    r.raise_for_status()
    return r.json()["text"].strip()


def transcrever(audio):
    # tenta o motor escolhido; se falhar, usa o outro como reserva
    ordem = ["pc", "groq"] if ler_cfg()["motor"] == "pc" else ["groq", "pc"]
    for m in ordem:
        try:
            if m == "pc" and modelo is not None:
                return pelo_pc(audio)
            if m == "groq" and chave_groq():
                return pela_groq(audio)
        except Exception as e:
            logging.exception("Falha no motor %s: %s", m, e)
    return ""


def colar(texto, enviar=False, espaco=True):
    global ultimo_colado
    import keyboard, pyperclip
    # espera soltar Ctrl/Alt/Win/Shift para nao virar outro atalho (ex.: Win+V)
    fim = time.time() + 2
    while time.time() < fim and any(keyboard.is_pressed(k) for k in ("ctrl", "alt", "windows", "shift")):
        time.sleep(0.02)
    try:
        antigo = pyperclip.paste()
    except Exception:
        antigo = ""
    final = texto + (" " if espaco and not enviar else "")
    pyperclip.copy(final)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    ultimo_colado = len(final)
    if enviar:
        time.sleep(0.15)
        keyboard.send("enter")
    time.sleep(0.4)
    pyperclip.copy(antigo)  # devolve o que estava na area de transferencia


# ---------------- Ler texto selecionado (traduzido) ----------------
lendo = False
parar_leitura = threading.Event()


def esperar_soltar():
    import keyboard
    fim = time.time() + 2
    while time.time() < fim and any(keyboard.is_pressed(k) for k in ("ctrl", "alt", "windows", "shift")):
        time.sleep(0.02)


def pegar_selecao():
    import keyboard, pyperclip
    esperar_soltar()
    try:
        antigo = pyperclip.paste()
    except Exception:
        antigo = ""
    pyperclip.copy("")
    keyboard.send("ctrl+c")
    txt, fim = "", time.time() + 1
    while time.time() < fim and not txt:
        time.sleep(0.03)
        txt = pyperclip.paste()
    pyperclip.copy(antigo)
    return txt.strip()


def traduzir(txt):
    import requests
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers={"Authorization": f"Bearer {chave_groq()}"},
                      json={"model": "openai/gpt-oss-20b", "reasoning_effort": "low", "temperature": 0.2,
                            "messages": [
                                {"role": "system", "content": "Traduza o texto do usuário para português do Brasil, "
                                 "de forma natural e fiel. Se já estiver em português, devolva igual. "
                                 "Responda somente com a tradução, sem comentários."},
                                {"role": "user", "content": txt}]}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def contexto_usuario():
    sobre = ler_cfg().get("sobre_mim", "").strip()
    return f"(Sobre o usuário: {sobre}) " if sobre else ""


def ia_groq(sistema, usuario):
    import requests
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers={"Authorization": f"Bearer {chave_groq()}"},
                      json={"model": "openai/gpt-oss-120b", "reasoning_effort": "low", "temperature": 0.4,
                            "messages": [{"role": "system", "content": sistema},
                                         {"role": "user", "content": usuario}]}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def adicionar_dicionario(instrucao, selecionado):
    """F8 + "adiciona no dicionário Ubiquiti"  ou  selecionar a palavra + F8 + "adiciona no dicionário".
    Devolve True se era um pedido de dicionario."""
    import re
    m = re.match(r"^\s*(adiciona|adicionar|adicione|coloca|colocar|coloque|bota|botar|p[oõ]e|salva|salvar)\s+"
                 r"(isso\s+|isto\s+|a palavra\s+)?(no|ao|n[oa] meu)\s+dicion[aá]rio[\s:,.-]*(.*)$", instrucao, re.IGNORECASE)
    if not m:
        return False
    palavra = (m.group(4) or "").strip(" .,!?\"'")
    if not palavra:
        palavra = (selecionado or "").strip()
    if not palavra or "\n" in palavra or len(palavra) > 60:
        bip("erro")
        return True
    ler_dicionario()
    with open(DICIONARIO, "a", encoding="utf-8") as f:
        f.write("\n" + palavra)
    logging.info("Dicionario: adicionado '%s'", palavra)
    bip("inicio")
    return True


def processar_comando(audio):
    """Tecla de comando: com texto selecionado, reescreve conforme a instrucao falada.
    Sem nada selecionado, escreve um texto novo a partir da instrucao."""
    try:
        instrucao = aplicar_trocas(transcrever(audio))
        logging.info("Comando: %s", instrucao)
        if not instrucao:
            bip("erro"); return
        selecionado = pegar_selecao()
        if adicionar_dicionario(instrucao, selecionado):
            return
        if selecionado:
            resultado = ia_groq(
                "Você reescreve textos do usuário. " + contexto_usuario() +
                "Aplique a instrução ao texto, mantendo o idioma do texto, a não ser que a instrução peça outro. "
                "Responda SOMENTE com o texto final, sem aspas e sem comentários.",
                f"Instrução: {instrucao}\n\nTexto:\n{selecionado}")
        else:
            resultado = ia_groq(
                "Você escreve textos para o usuário " + contexto_usuario() +
                "a partir de um pedido falado: mensagens de WhatsApp, e-mails, respostas a clientes. "
                "Português do Brasil, natural e direto. Responda SOMENTE com o texto pronto para colar.",
                instrucao)
        salvar_historico(resultado)
        colar(resultado, espaco=False)    # com texto selecionado, o colar substitui a selecao
    except Exception as e:
        logging.exception("Falha no comando: %s", e)
        bip("erro")
    finally:
        mudar_estado("pronto")


def tocar_mp3(arq):
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    mci("close fala", None, 0, None)
    mci(f'open "{arq}" type mpegvideo alias fala', None, 0, None)
    mci("play fala", None, 0, None)
    buf = ctypes.create_unicode_buffer(64)
    while not parar_leitura.is_set():
        mci("status fala mode", buf, 64, None)
        if buf.value != "playing":
            break
        time.sleep(0.1)
    mci("close fala", None, 0, None)


def falar(txt, voz=None):
    arq = os.path.join(BASE, "fala.mp3")
    try:
        import asyncio, edge_tts
        asyncio.run(edge_tts.Communicate(txt, voz or ler_cfg()["voz"]).save(arq))
    except Exception as e:
        # reserva: voz Maria do proprio Windows (funciona sem internet)
        logging.warning("Voz neural falhou (%s); usando a voz do Windows", e)
        tmp = os.path.join(BASE, "fala.txt")
        open(tmp, "w", encoding="utf-8").write(txt)
        p = subprocess.Popen(["powershell", "-NoProfile", "-Command",
                              "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                              f"$s.Speak([IO.File]::ReadAllText('{tmp}'))"], creationflags=0x08000000)
        while p.poll() is None:
            if parar_leitura.is_set():
                p.kill()
            time.sleep(0.1)
        return
    if not parar_leitura.is_set():
        tocar_mp3(arq)


def ler_selecao():
    global lendo
    lendo = True
    parar_leitura.clear()
    mudar_estado("pensando")
    try:
        txt = pegar_selecao()
        if not txt:
            bip("erro"); return
        t = time.time()
        traducao = traduzir(txt) if chave_groq() else txt
        logging.info("Leitura (%.2fs para traduzir): %s", time.time() - t, traducao[:200])
        mudar_estado("lendo")
        falar(traducao)
    except Exception as e:
        logging.exception("Falha ao ler selecao: %s", e)
        bip("erro")
    finally:
        lendo = False
        mudar_estado("pronto")


# ---------------- Visual: icone, sons, pilula flutuante ----------------
ATALHO_INICIAR = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup\VozLivre.vbs")
PYTHONW = sys.executable.replace("python.exe", "pythonw.exe")
ICO = os.path.join(BASE, "voz_livre.ico")
icone = None
estado = "carregando"
nivel = 0.0                       # volume do microfone (para a onda da pilula)
sair_evt = threading.Event()
CORES = {"carregando": (120, 120, 130), "pronto": (124, 92, 255), "gravando": (255, 69, 58),
         "pensando": (255, 184, 0), "lendo": (64, 156, 255), "comando": (190, 120, 255)}


def desenhar(cor, tam=64):
    from PIL import Image, ImageDraw
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    claro = tuple(min(255, c + 60) for c in cor)
    for i in range(S // 2, 0, -1):            # circulo com degrade
        k = i / (S / 2)
        c = tuple(int(claro[j] * (1 - k) + cor[j] * k) for j in range(3))
        d.ellipse((S / 2 - i, S / 2 - i, S / 2 + i, S / 2 + i), fill=c)
    d.rounded_rectangle((100, 52, 156, 150), radius=28, fill="white")      # microfone
    d.arc((72, 92, 184, 182), 0, 180, fill="white", width=14)
    d.line((128, 182, 128, 208), fill="white", width=14)
    d.line((96, 208, 160, 208), fill="white", width=14)
    return img.resize((tam, tam), Image.LANCZOS)


def mudar_estado(novo):
    global estado
    estado = novo
    if icone:
        icone.icon = desenhar(CORES[novo])
        nomes = {"carregando": "carregando...", "pronto": "pronto", "gravando": "ouvindo", "pensando": "processando", "lendo": "lendo", "comando": "ouvindo comando"}
        icone.title = f"Voz Livre - {nomes[novo]}"


def gerar_sons():
    import numpy as np
    sons = {"inicio": (620, 930), "fim": (930, 620), "erro": (300, 200)}
    for nome, (f1, f2) in sons.items():
        arq = os.path.join(BASE, f"som_{nome}.wav")
        if os.path.exists(arq):
            continue
        sr = 44100
        t = np.arange(int(sr * 0.11)) / sr
        f = np.linspace(f1, f2, len(t))
        onda = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.minimum(1, t * 400) * np.exp(-t * 28) * 0.22
        w = wave.open(arq, "wb")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((onda * 32767).astype(np.int16).tobytes())
        w.close()


def bip(nome):
    import winsound
    arq = os.path.join(BASE, f"som_{nome}.wav")
    try:
        winsound.PlaySound(arq, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def pilula():
    """Janela flutuante feita direto na API do Windows (sem Tkinter):
    transparencia real por pixel (bordas lisas + sombra), nao rouba o foco,
    e pode ser arrastada como uma janela normal. Tamanho, opacidade e posicao ficam no config.json."""
    import ctypes, ctypes.wintypes as wt, math, collections
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)     # nitido em telas com zoom (125%, 150%...)
    except Exception:
        pass
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    g32 = ctypes.WinDLL("gdi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                    ("lpszClassName", wt.LPCWSTR)]

    class BLEND(ctypes.Structure):
        _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_ubyte)]

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    u32.DefWindowProcW.restype = LRESULT
    u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    u32.CreateWindowExW.restype = wt.HWND
    u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    u32.LoadCursorW.restype = wt.HANDLE
    u32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
    u32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    u32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
    u32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    u32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    u32.DestroyWindow.argtypes = [wt.HWND]
    u32.GetDC.restype = wt.HDC
    u32.GetDC.argtypes = [wt.HWND]
    u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    u32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), wt.HDC,
                                        ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.POINTER(BLEND), wt.DWORD]
    g32.CreateDIBSection.restype = wt.HBITMAP
    g32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p),
                                     wt.HANDLE, wt.DWORD]
    g32.CreateCompatibleDC.restype = wt.HDC
    g32.CreateCompatibleDC.argtypes = [wt.HDC]
    g32.SelectObject.restype = wt.HGDIOBJ
    g32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    g32.DeleteObject.argtypes = [wt.HGDIOBJ]
    g32.DeleteDC.argtypes = [wt.HDC]
    k32.GetModuleHandleW.restype = wt.HMODULE
    k32.GetModuleHandleW.argtypes = [wt.LPCWSTR]

    dpi = u32.GetDpiForSystem() / 96 if hasattr(u32, "GetDpiForSystem") else 1.0
    sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
    BW, BH, M, S = 260, 52, 14, 3            # pilula base, margem da sombra, supersample
    atual = {"W": 0, "H": 0, "x": 0, "y": 0, "alpha": 242, "cfg_em": 0, "mostrar_ate": 0}
    hwnd_ref = [None]

    def salvar_posicao():
        r = wt.RECT()
        u32.GetWindowRect(hwnd_ref[0], ctypes.byref(r))
        atual.update(x=r.left, y=r.top)
        c = ler_cfg()
        c["pilula_x"], c["pilula_y"] = r.left, r.top
        salvar_cfg(c)

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == 0x0084:                     # WM_NCHITTEST: a pilula inteira serve de "barra de titulo" (arrastar)
            return 2                          # HTCAPTION
        if msg == 0x0021:                     # WM_MOUSEACTIVATE: clicar nao rouba o foco
            return 3                          # MA_NOACTIVATE
        if msg in (0x00A3, 0x00A4, 0x00A5, 0x007B):   # duplo clique / botao direito: nao faz nada
            return 0
        if msg == 0x0232:                     # WM_EXITSIZEMOVE: terminou de arrastar
            salvar_posicao()
            return 0
        return u32.DefWindowProcW(hwnd, msg, wparam, lparam)
    proc = WNDPROC(wndproc)                   # guardar referencia (senao o Python apaga)

    hinst = k32.GetModuleHandleW(None)
    wc = WNDCLASSW(0, proc, 0, 0, hinst, None, u32.LoadCursorW(None, ctypes.c_void_p(32646)), None, None,
                   "PilulaVozLivre")             # 32646 = cursor de mover
    u32.RegisterClassW(ctypes.byref(wc))
    WS_EX = 0x00000008 | 0x00080000 | 0x00000080 | 0x08000000   # topmost, layered, toolwindow, noactivate
    hwnd = u32.CreateWindowExW(WS_EX, "PilulaVozLivre", "Pilula", 0x80000000, 0, 0, 1, 1, None, None, hinst, None)
    hwnd_ref[0] = hwnd

    def mostrar_imagem(img):
        """img: RGBA no tamanho da janela. Envia ao Windows com alfa por pixel."""
        w, h = img.size
        a = np.asarray(img, dtype=np.float32)
        a[..., :3] *= a[..., 3:4] / 255.0                  # alfa pre-multiplicado
        bgra = np.ascontiguousarray(a[..., [2, 1, 0, 3]]).astype(np.uint8).tobytes()
        bmi = BMIH(ctypes.sizeof(BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        tela = u32.GetDC(None)
        mem = g32.CreateCompatibleDC(tela)
        bmp = g32.CreateDIBSection(tela, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, bgra, len(bgra))
        antigo = g32.SelectObject(mem, bmp)
        ok = u32.UpdateLayeredWindow(hwnd, tela, ctypes.byref(wt.POINT(atual["x"], atual["y"])),
                                     ctypes.byref(wt.SIZE(w, h)), mem, ctypes.byref(wt.POINT(0, 0)), 0,
                                     ctypes.byref(BLEND(0, 0, atual["alpha"], 1)), 2)
        if not ok and not atual.get("avisou"):
            atual["avisou"] = True
            logging.warning("Pilula: UpdateLayeredWindow falhou (erro %s)", ctypes.get_last_error())
        g32.SelectObject(mem, antigo)
        g32.DeleteObject(bmp)
        g32.DeleteDC(mem)
        u32.ReleaseDC(None, tela)

    try:
        fonte = ImageFont.truetype("seguisb.ttf", 15 * S)
    except Exception:
        fonte = ImageFont.truetype("segoeui.ttf", 15 * S)
    textos = {"gravando": "Ouvindo", "pensando": "Escrevendo", "lendo": "Lendo", "comando": "Comando"}

    # sombra suave: calculada uma vez so (o desenho e sempre no tamanho base e depois reduzido)
    CW, CH = (BW + 2 * M) * S, (BH + 2 * M) * S
    sombra = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((M * S, (M + 3) * S, (M + BW) * S, (M + BH + 3) * S),
                                             radius=(BH // 2) * S, fill=(0, 0, 0, 90))
    sombra = sombra.filter(ImageFilter.GaussianBlur(3 * S))
    sombra.putalpha(sombra.getchannel("A").point(lambda v: 0 if v < 4 else v))   # sem "nevoa" no fundo

    def aplicar_cfg():
        c = ler_cfg()
        esc = max(0.6, min(2.0, float(c.get("pilula_escala", 1.0)))) * dpi
        W, H = int((BW + 2 * M) * esc), int((BH + 2 * M) * esc)
        x, y = c.get("pilula_x"), c.get("pilula_y")
        if x is None or y is None:
            x, y = (sw - W) // 2, sh - H - int(70 * dpi)        # padrao: embaixo, no meio
        x, y = max(-M, min(sw - 60, int(x))), max(-M, min(sh - 30, int(y)))   # nunca some da tela
        atual.update(W=W, H=H, x=x, y=y)
        atual["alpha"] = int(255 * max(0.3, min(1.0, float(c.get("pilula_opacidade", 0.95)))))
        atual["mostrar_ate"] = float(c.get("pilula_mostrar_ate", 0))

    hist = collections.deque([0.0] * 20, maxlen=20)

    def desenhar_quadro(e, t):
        texto = textos.get(e, "Arraste-me")
        cor = CORES[e] if e in textos else CORES["pronto"]
        img = sombra.copy()
        d = ImageDraw.Draw(img)
        ox, oy = M * S, M * S
        d.rounded_rectangle((ox, oy, ox + BW * S, oy + BH * S), radius=(BH // 2) * S,
                            fill=(20, 20, 26, 255), outline=(62, 62, 76, 255), width=S)
        cy = oy + BH * S / 2
        cx = ox + 26 * S
        r = (5.5 + 1.5 * math.sin(t * 6)) * S
        d.ellipse((cx - r * 1.9, cy - r * 1.9, cx + r * 1.9, cy + r * 1.9), fill=tuple(c // 4 for c in cor) + (255,))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=cor + (255,))
        d.text((ox + 46 * S, cy), texto, font=fonte, fill=(240, 240, 246, 255), anchor="lm")
        n, bw, gap, x0 = 20, 3 * S, 2 * S, ox + 142 * S
        for i in range(n):
            if e in ("gravando", "comando"):
                v = hist[i]
            elif e == "lendo":
                v = 0.35 + 0.3 * math.sin(t * 7 + i * 0.6) * math.sin(t * 2.3 + i * 0.25)
            elif e in textos:
                v = 0.12 + 0.12 * (1 + math.sin(t * 9 - i * 0.45)) / 2
            else:                                       # modo posicionar
                v = 0.2 + 0.15 * math.sin(t * 3 + i * 0.3)
            h = max(3 * S, v * 30 * S)
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, cy - h / 2, x + bw, cy + h / 2), radius=bw // 2,
                                fill=((240, 240, 246) if e in ("gravando", "comando") else cor) + (255,))
        # reduz com alfa pre-multiplicado (RGBa) para as bordas ficarem lisas, sem halo escuro
        return img.convert("RGBa").resize((atual["W"], atual["H"]), Image.LANCZOS).convert("RGBA")

    def vazio():
        return Image.new("RGBA", (max(1, atual["W"]), max(1, atual["H"])), (0, 0, 0, 0))

    aplicar_cfg()
    mostrar_imagem(vazio())
    u32.ShowWindow(hwnd, 4)                   # SW_SHOWNOACTIVATE (fica "visivel", mas 100% transparente)
    t0, vis, cfg_em = time.time(), False, 0.0
    msg = wt.MSG()
    while not sair_evt.is_set():
        while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):   # PM_REMOVE
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        if time.time() - cfg_em > 0.5:                              # pega mudancas das Configuracoes
            aplicar_cfg(); cfg_em = time.time()
        e = estado
        mostrar = e in textos or time.time() < atual["mostrar_ate"]
        if mostrar:
            if not vis:
                hist.extend([0.0] * 20); vis = True
            hist.append(min(1.0, (nivel * 18) ** 0.7))
            mostrar_imagem(desenhar_quadro(e, time.time() - t0))
        elif vis:
            mostrar_imagem(vazio()); vis = False
        time.sleep(0.033)
    u32.DestroyWindow(hwnd)


# ---------------- Teclado + gravacao ----------------
def laco_teclado():
    import keyboard, sounddevice as sd, numpy as np
    import collections
    pedacos, gravando = [], False
    antes = collections.deque(maxlen=8)          # ~0,4 s de audio guardado ANTES de apertar a tecla

    def cb(indata, frames, t, status):
        global nivel
        nivel = float(np.sqrt(np.mean(indata ** 2)))
        if gravando:
            pedacos.append(indata[:, 0].copy())
        else:
            antes.append(indata[:, 0].copy())

    stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=800, callback=cb)
    stream.start()
    tecla, tecla_ler, tecla_colar, tecla_cmd, ultimo_cfg, ler_antes, colar_antes = "", "", "", "", 0, False, False
    modo = "ditado"                               # "ditado" ou "comando" (tecla de reescrever)
    _c = ler_cfg()
    motor_atual = [(_c["motor"], _c["modelo"])]   # o main() ja carregou este
    while not sair_evt.is_set():
        if time.time() - ultimo_cfg > 1:          # rele a config 1x por segundo
            cfg = ler_cfg()
            tecla, tecla_ler, tecla_colar, tecla_cmd = cfg["tecla"], cfg["tecla_ler"], cfg["tecla_colar"], cfg["tecla_comando"]
            ultimo_cfg = time.time()
            if (cfg["motor"], cfg["modelo"]) != motor_atual[0] and modelo_status != "carregando":
                motor_atual[0] = (cfg["motor"], cfg["modelo"])          # mudou nas configuracoes: recarrega
                threading.Thread(target=carregar_modelo, daemon=True).start()
            if estado == "carregando" and (modelo_status != "carregando" or chave_groq()):
                mudar_estado("pronto")   # Groq ja funciona enquanto o modelo do PC carrega
        try:
            apertado = keyboard.is_pressed(tecla)
        except Exception:
            apertado = False
        try:
            ler_agora = keyboard.is_pressed(tecla_ler)
        except Exception:
            ler_agora = False
        if ler_agora and not ler_antes:            # apertou a tecla de leitura
            if lendo:
                parar_leitura.set()                # apertar de novo para de ler
            elif estado == "pronto":
                threading.Thread(target=ler_selecao, daemon=True).start()
        ler_antes = ler_agora
        try:
            colar_agora = keyboard.is_pressed(tecla_colar)
        except Exception:
            colar_agora = False
        if colar_agora and not colar_antes and estado == "pronto":
            threading.Thread(target=colar_ultimo, daemon=True).start()   # cola de novo o ultimo ditado
        colar_antes = colar_agora
        try:
            cmd_agora = keyboard.is_pressed(tecla_cmd)
        except Exception:
            cmd_agora = False
        if (apertado or cmd_agora) and not gravando and estado == "pronto":
            modo = "comando" if cmd_agora else "ditado"
            pedacos.clear(); pedacos.extend(antes); gravando = True
            mudar_estado("comando" if modo == "comando" else "gravando"); bip("inicio")
        elif gravando and not (apertado if modo == "ditado" else cmd_agora):
            gravando = False; bip("fim")
            audio = np.concatenate(pedacos) if pedacos else np.zeros(0, dtype="float32")
            if len(audio) > 16000 * 0.8:            # ignora toque rapido sem fala (inclui os 0,4 s de antes)
                mudar_estado("pensando")
                alvo = processar_comando if modo == "comando" else processar
                threading.Thread(target=alvo, args=(audio,), daemon=True).start()
            else:
                mudar_estado("pronto")
        time.sleep(0.02)


HISTORICO = os.path.join(BASE, "historico.jsonl")


def salvar_historico(texto):
    from datetime import datetime
    with open(HISTORICO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"quando": datetime.now().strftime("%d/%m %H:%M"), "texto": texto}, ensure_ascii=False) + "\n")


def ler_historico(n=10):
    try:
        linhas = open(HISTORICO, encoding="utf-8").read().strip().split("\n")
        return [json.loads(l) for l in reversed(linhas[-n:]) if l]
    except Exception:
        return []


def colar_ultimo():
    h = ler_historico(1)
    if h:
        colar(h[0]["texto"])
    else:
        bip("erro")


# Comandos falados: viram pontuacao / acoes
COMANDOS = [
    (r"[ \t]*\bnovo par[aá]grafo\b[ \t,.]*", "\n\n"),
    (r"[ \t]*\b(nova linha|pula linha|pular linha)\b[ \t,.]*", "\n"),
    (r"[ \t]*\bponto de interroga[cç][aã]o\b[ \t,.]*", "? "),
    (r"[ \t]*\bponto de exclama[cç][aã]o\b[ \t,.]*", "! "),
    (r"[ \t]*\bponto final\b[ \t,.]*", ". "),
    (r"[ \t]*\bdois pontos\b[ \t,.]*", ": "),
    (r"[ \t,]*\bv[ií]rgula\b[ \t,.]*", ", "),
]
FRASES_APAGAR = ("apaga isso", "apagar isso", "apague isso", "cancela", "cancelar")


def comandos_voz(texto):
    """Devolve (texto, enviar, apagar)."""
    import re
    limpo = re.sub(r"[^\w\s]", "", texto).strip().lower()
    if limpo in FRASES_APAGAR:
        return "", False, True
    enviar = bool(ler_cfg().get("enviar_auto", False))
    m = re.search(r"[\s,.]*\b(envia|enviar|manda|mandar)\s+(a\s+)?mensagem[\s.!]*$", texto, re.IGNORECASE)
    if m:
        texto, enviar = texto[:m.start()], True
    for padrao, troca in COMANDOS:
        texto = re.sub(padrao, troca, texto, flags=re.IGNORECASE)
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"(^|[.?!]\s+|\n)([a-zà-ú])", lambda g: g.group(1) + g.group(2).upper(), texto)
    return texto.strip(" "), enviar, False


ultimo_colado = 0


def apagar_ultimo():
    import keyboard
    esperar_soltar()
    for _ in range(ultimo_colado):
        keyboard.send("backspace")
        time.sleep(0.004)


def processar(audio):
    try:
        t = time.time()
        texto = aplicar_trocas(transcrever(audio))
        if "Termos:" in texto and "Ditado em português" in texto:
            texto = ""          # o Whisper repetiu a dica (acontece com silencio)
        logging.info("%.2fs de audio em %.2fs: %s", len(audio) / 16000, time.time() - t, texto)
        texto, enviar, apagar = comandos_voz(texto)
        if apagar:
            apagar_ultimo()
        elif texto:
            salvar_historico(texto)
            colar(texto, enviar)
        elif enviar:                      # falou so "envia mensagem"
            import keyboard
            esperar_soltar(); keyboard.send("enter")
        else:
            bip("erro")
    finally:
        mudar_estado("pronto")


def abrir_config(*_):
    subprocess.Popen([PYTHONW, os.path.join(BASE, "config_ui.py")])


def abrir_sobre(*_):
    subprocess.Popen([PYTHONW, os.path.join(BASE, "sobre.py")])


def inicia_com_windows(*_):
    return os.path.exists(ATALHO_INICIAR)


def alternar_iniciar(*_):
    if inicia_com_windows():
        os.remove(ATALHO_INICIAR)
    else:
        with open(ATALHO_INICIAR, "w", encoding="utf-8") as f:
            f.write(f'CreateObject("WScript.Shell").Run """{PYTHONW}"" ""{os.path.abspath(__file__)}""", 0\n')


def sair(i, _):
    sair_evt.set()
    i.stop()


def mostrar_pilula_para_posicionar(*_):
    c = ler_cfg()
    c["pilula_mostrar_ate"] = time.time() + 15      # aparece 15 s para arrastar
    salvar_cfg(c)


def menu_historico():
    import pystray, pyperclip
    itens = []
    for h in ler_historico(10):
        resumo = h["texto"].replace("\n", " ")
        resumo = resumo[:48] + ("…" if len(resumo) > 48 else "")
        itens.append(pystray.MenuItem(f'{h["quando"]}   {resumo}', (lambda t: lambda *_: pyperclip.copy(t))(h["texto"])))
    if not itens:
        itens.append(pystray.MenuItem("(nada ainda)", None, enabled=False))
    itens.append(pystray.Menu.SEPARATOR)
    itens.append(pystray.MenuItem("Clique num item para copiar", None, enabled=False))
    return itens


def main():
    global icone
    import pystray, ctypes
    # so uma copia aberta: se ja estiver rodando, abre as Configuracoes e sai
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, "VozLivre_unico")
    if ctypes.get_last_error() == 183:          # ERROR_ALREADY_EXISTS
        abrir_config()
        return
    primeira_vez = not os.path.exists(CFG)
    if primeira_vez:
        # comeca sem baixar nada; a pessoa escolhe nas Configuracoes se quer o modelo no PC
        salvar_cfg({**PADRAO, "motor": "groq"})
    gerar_sons()
    ler_dicionario()            # cria o dicionario.txt na primeira vez
    if not os.path.exists(ICO):
        desenhar(CORES["pronto"], 256).save(ICO, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    threading.Thread(target=carregar_modelo, daemon=True).start()
    threading.Thread(target=laco_teclado, daemon=True).start()
    menu = pystray.Menu(
        pystray.MenuItem("Configurações", abrir_config, default=True),
        pystray.MenuItem("Histórico", pystray.Menu(menu_historico)),
        pystray.MenuItem("Posicionar pílula", mostrar_pilula_para_posicionar),
        pystray.MenuItem("Editar dicionário", lambda *_: os.startfile(DICIONARIO)),
        pystray.MenuItem("Iniciar com o Windows", alternar_iniciar, checked=inicia_com_windows),
        pystray.MenuItem("Abrir pasta", lambda *_: os.startfile(BASE)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Sobre o Voz Livre (v{VERSAO})", abrir_sobre),
        pystray.MenuItem("Sair", sair),
    )
    icone = pystray.Icon("voz_livre", desenhar(CORES["carregando"]), "Voz Livre - carregando...", menu)
    icone.run_detached()
    if primeira_vez:
        abrir_config()
    pilula()            # a pilula roda na linha principal (tkinter)
    os._exit(0)


if __name__ == "__main__":
    main()
