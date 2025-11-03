# =========================================
# Sessão 0.0 – Parâmetros gerais (via ENV)
# =========================================
import os

# Credenciais SGI
USUARIO_SGI = os.environ.get("SGI_USERNAME", "")
SENHA_SGI   = os.environ.get("SGI_PASSWORD", "")

# Google Sheets / Drive
PLANILHA_ID             = os.environ.get("PLANILHA_ID", "")
ABA_CONTROLE            = os.environ.get("ABA_CONTROLE", "PROCESSO ENTRADA")
ID_PASTA_GOOGLE_DRIVE   = os.environ.get("ID_PASTA_GOOGLE_DRIVE", "")

# Caminhos (container)
LOGS_DIR        = os.environ.get("LOGS_DIR", "/app/logs")
DOWNLOAD_DIR    = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
PASTA_LOCAL_XML = os.path.join(DOWNLOAD_DIR, "xml")

# Criar diretórios necessários
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PASTA_LOCAL_XML, exist_ok=True)

# =========================================
# Sessão 1.0 – Bibliotecas
# =========================================
import re, time, glob, logging
from datetime import datetime as dt
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.service import Service
from google.oauth2 import service_account
from googleapiclient.discovery import build
import xml.etree.ElementTree as ET

# =========================================
# Sessão 1.1 – Logging
# =========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, dt.now().strftime("log_%Y-%m-%d_%H-%M-%S.txt")), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# =========================================
# Sessão 2.0 – Google Sheets util
# =========================================
from app.google_sheets_auth import load_sa_credentials, sheets_api

SCOPES_SHEETS = ["https://www.googleapis.com/auth/spreadsheets"]
creds_sheets   = load_sa_credentials(SCOPES_SHEETS)
SHEETS         = sheets_api(creds_sheets)

COL = {  # índice zero-based na planilha
    "NUMERO NF": 0,  "DATA EMISSÃO NF": 1, "XML DRIVE": 2,
    "XML IMPORTADA SGI": 3, "XML VINCULADA SGI": 4,
    "XML ENTRADA SALVA SGI": 5, "XML BOLETO SALVO SGI": 6, 
    "LINK LANÇAMENTO SGI": 7,
}

def _read_sheet():
    return SHEETS.values().get(
        spreadsheetId=PLANILHA_ID,
        range=f"'{ABA_CONTROLE}'!A1:J"
    ).execute().get("values", [])

def _update_cell(row_idx, col_idx, value):
    rng = f"'{ABA_CONTROLE}'!{chr(ord('A')+col_idx)}{row_idx+1}"
    # Transforma strings em booleanos apenas se for necessário
    if value is True or value is False:
        value_to_send = value
    elif isinstance(value, str):
        v = value.strip().upper()
        if v in ("VERDADEIRO", "TRUE", "SIM", "✓"):
            value_to_send = True
        elif v in ("FALSO", "FALSE", "NAO", "NÃO", "NO", "X"):
            value_to_send = False
        else:
            value_to_send = value
    else:
        value_to_send = value
    SHEETS.values().update(
        spreadsheetId=PLANILHA_ID, range=rng,
        valueInputOption="RAW", body={"values": [[value_to_send]]}
    ).execute()

def _read_cell(row_idx, col_idx, default=""):
    """Lê uma célula da planilha sem estourar IndexError quando a linha é “curta” (trailing empties)."""
    vals = _read_sheet()
    if 0 <= row_idx < len(vals):
        row = vals[row_idx]
        if col_idx < len(row):
            return row[col_idx]
    return default


def _get_or_create_row(nf, data_emissao=None):
    vals = _read_sheet()
    empty_idx = None

    for idx, row in enumerate(vals[1:], start=1):   # pula cabeçalho
        if len(row) > 0 and row[0] == nf:
            # Atualiza data se não estava preenchido
            if data_emissao and (len(row) < 2 or not row[1]):
                _update_cell(idx, COL["DATA EMISSÃO NF"], data_emissao)
            return idx
        if empty_idx is None and (len(row) == 0 or row[0] == ""):
            empty_idx = idx

    # --- preenche linha vazia encontrada ---
    if empty_idx is not None:
        existing = vals[empty_idx] if empty_idx < len(vals) else []
        new_row = existing + [""] * (10 - len(existing))
        new_row[COL["NUMERO NF"]] = nf
        if data_emissao: new_row[COL["DATA EMISSÃO NF"]] = data_emissao

        SHEETS.values().update(
            spreadsheetId=PLANILHA_ID,
            range=f"'{ABA_CONTROLE}'!A{empty_idx+1}:J{empty_idx+1}",
            valueInputOption="RAW",
            body={"values": [new_row]}
        ).execute()
        return empty_idx

    # --- se não havia linha vazia, acrescenta ---
    new = [""] * 10
    new[COL["NUMERO NF"]] = nf
    if data_emissao: new[COL["DATA EMISSÃO NF"]] = data_emissao

    SHEETS.values().append(
        spreadsheetId=PLANILHA_ID, range=f"'{ABA_CONTROLE}'!A1",
        valueInputOption="RAW", body={"values": [new]}
    ).execute()
    return len(vals)

# =========================================
# Sessão 3.0 – Download XMLs (preenche col. XML DRIVE)
# =========================================
def baixar_xmls_drive():
    from app.google_sheets_auth import load_sa_credentials
    os.makedirs(PASTA_LOCAL_XML, exist_ok=True)
    creds_drive = load_sa_credentials(["https://www.googleapis.com/auth/drive"])
    drive = build("drive", "v3", credentials=creds_drive, cache_discovery=False)
    q = (
        f"'{ID_PASTA_GOOGLE_DRIVE}' in parents "
        "and trashed = false "
        "and mimeType != 'application/vnd.google-apps.folder' "
        "and name contains '.xml' "
        "and not name contains '(FEITO)'"
    )

    for f in drive.files().list(q=q, fields="files(id,name)").execute().get("files", []):
        nome    = f["name"]
        destino = os.path.join(PASTA_LOCAL_XML, nome)

        if os.path.exists(destino) or os.path.exists(destino.replace(".xml", "(FEITO).xml")):
            continue

        data = drive.files().get_media(fileId=f["id"]).execute()
        with open(destino, "wb") as fh:
            fh.write(data)
        logging.info(f"Baixado {nome}")

        try:
            with open(destino, "rb") as fh:
                tree = ET.parse(fh)
            ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
            nf  = tree.find(".//nfe:ide/nfe:nNF", ns).text
            d_emis = tree.find(".//nfe:ide/nfe:dhEmi", ns).text[:10]
            linha = _get_or_create_row(
                nf,
                dt.strptime(d_emis, "%Y-%m-%d").strftime("%d/%m/%Y")
            )
            _update_cell(linha, COL["XML DRIVE"], True)
        except Exception as e:
            logging.warning(f"Não extrai dados de {nome}: {e}")

# =========================================
# Sessão 4.0 – Funções SGI genéricas
# =========================================
def novo_driver() -> webdriver.Chrome:
    import os, tempfile, shutil, glob, time
    from selenium.webdriver.chrome.service import Service

    CHROME_BIN = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    CHROMEDRIVER_BIN = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    if not os.path.exists(CHROME_BIN):
        raise RuntimeError(f"Chromium não encontrado em {CHROME_BIN}.")
    if not os.path.exists(CHROMEDRIVER_BIN):
        raise RuntimeError(f"Chromedriver não encontrado em {CHROMEDRIVER_BIN}.")

    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_BIN

    # Flags essenciais p/ container
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # PERFIL: gere um diretório ÚNICO por execução para evitar o erro "user data dir in use"
    base_profile = os.environ.get("CHROME_USER_DIR_BASE", "/app/chrome-profile")
    os.makedirs(base_profile, exist_ok=True)
    unique_profile = tempfile.mkdtemp(prefix="run_", dir=base_profile)
    options.add_argument(f"--user-data-dir={unique_profile}")

    # Downloads (isolados por execução)
    dl_dir = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
    os.makedirs(dl_dir, exist_ok=True)
    options.add_experimental_option("prefs", {"download.default_directory": dl_dir})

    # Workaround: se alguém passar um USER_DATA_DIR fixo por env, limpamos "Singleton*"
    # (não é necessário com o diretório único, mas deixa resiliente)
    def _unlock_profile(path: str):
        for p in glob.glob(os.path.join(path, "Singleton*")):
            try: os.remove(p)
            except Exception: pass

    try:
        _unlock_profile(unique_profile)
    except Exception:
        pass

    service = Service(CHROMEDRIVER_BIN)
    driver = webdriver.Chrome(service=service, options=options)

    # Anexa o caminho do perfil ao objeto p/ limpar depois, se quiser
    driver._lebebe_profile_dir = unique_profile
    return driver

def login(driver, tentativas_max=3):
    """
    Faz login no SGI e garante que chega à URL /home.
    Se a seleção de filial ou o botão 'Prosseguir' falhar, tenta de novo.
    """
    url_home = "https://smart.sgisistemas.com.br/home"
    w = WebDriverWait(driver, 15)

    for tentativa in range(1, tentativas_max + 1):
        try:
            driver.get("https://smart.sgisistemas.com.br/")
            # ---------- tela de usuário/senha ----------
            w.until(EC.presence_of_element_located((By.ID, "usuario"))).clear()
            driver.find_element(By.ID, "usuario").send_keys(USUARIO_SGI)
            driver.find_element(By.NAME, "senha").clear()
            driver.find_element(By.NAME, "senha").send_keys(SENHA_SGI, Keys.RETURN)

            # ---------- tela de filial ----------
            w.until(EC.presence_of_element_located((By.ID, "filial_id")))
            Select(driver.find_element(By.ID, "filial_id")).select_by_visible_text("LEBEBE DEPÓSITO (CD)")

            # clica em Prosseguir (pode precisar clicar 2× em alguns cenários)
            for _ in range(3):
                try:
                    driver.find_element(By.ID, "botao_prosseguir_informa_local_trabalho").click()
                    time.sleep(1.0)  # dá um respiro
                    if driver.current_url.startswith(url_home):
                        logging.info("Login SGI concluído (tentativa %s).", tentativa)
                        return
                except Exception:
                    pass  # botão sumiu / já clicou – tudo bem

            # Se não chegou na home, força refresh e tenta de novo
            logging.warning("Não chegou à página /home (tentativa %s). Repetindo login…", tentativa)

        except Exception as e:
            logging.error("Falha ao logar (tentativa %s): %s", tentativa, e)

        # pequena pausa antes da próxima tentativa
        time.sleep(2)

    raise RuntimeError(f"Falhou ao logar no SGI após {tentativas_max} tentativas.")

def safe_click(elemento, driver, timeout=5):
    """
    Clica no elemento; se um modal de confirmação (bootbox) estiver cobrindo,
    aperta o botão “confirm” do modal e tenta clicar de novo.
    """
    try:
        elemento.click()
        return
    except ElementClickInterceptedException:
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    '.bootbox.modal.fade.bootbox-confirm.in button[data-bb-handler="confirm"]'
                ))
            ).click()
            time.sleep(0.4)
            elemento.click()   # tenta novamente
        except Exception:
            raise  # se ainda falhar, deixa o erro subir

def _garantir_sessao(driver):
    if "smart.sgisistemas.com.br" not in driver.current_url:
        try: login(driver)
        except: pass


# =========================================
# Sessão 5.0 – Importar & Vincular
# =========================================
import re
def extrair_numero_nf(nome_arquivo):
    return re.match(r"^(\d+)", nome_arquivo).group(1)

def importar_xmls_em_lote(driver, arquivos_xml):
    logging.info("▶️ Iniciando automação de importação de TODOS os XMLs da pasta.")
    nfs_importadas = []
    wait = WebDriverWait(driver, 20)

    for arquivo in arquivos_xml:
        caminho_xml = os.path.join(PASTA_LOCAL_XML, arquivo)
        logging.info(f"===> Importando arquivo: {arquivo}")
        numero_nf = extrair_numero_nf(os.path.basename(arquivo))

        driver.get("https://smart.sgisistemas.com.br/importacoes_xml_nfe")
        time.sleep(2)

        try:
            # ---------- abre modal ----------
            botao_buscar = driver.find_element(By.ID, "novo_xml_nfe")
            botao_buscar.click()
            time.sleep(1)

            iframe = driver.find_element(By.ID, "iframe_modal")
            driver.switch_to.frame(iframe)
            time.sleep(1)

            # ---------- escolhe arquivo ----------
            botao_escolher = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "botao-upload-arquivo"))
            )
            botao_escolher.click()
            time.sleep(1)

            input_file = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "file_field_arquivo"))
            )
            input_file.send_keys(caminho_xml)
            logging.info(f"✅ Arquivo enviado: {caminho_xml}")

            # ---------- CNPJ diferente? ----------
            try:
                botao_sim = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-bb-handler="confirm"]'))
                )
                botao_sim.click()
                time.sleep(1)
            except Exception:
                pass

            # ---------- importar ----------
            botao_importar = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.btn.btn-success[type="submit"]'))
            )
            botao_importar.click()
            logging.info("✅ Cliquei em 'Importar'.")
            time.sleep(2)

            # ---------- já importado? ----------
            erro_já_importado = False
            try:
                alerta = driver.find_element(By.CSS_SELECTOR, ".alert-danger")
                if "Chave de Acesso já está em uso" in alerta.text:
                    erro_já_importado = True
                    logging.warning("⚠️ XML já havia sido importado!")
                    driver.find_element(By.CSS_SELECTOR, ".close").click()
                    time.sleep(1)
            except Exception:
                pass

            # ---------- renomeia local ----------
            def limpar_sufixo(nome):
                # Remove todos os sufixos FEITO/JÁ_IMPORTADO para não empilhar nomes
                return re.sub(r"(\(FEITO(_TMP)?\)|\(JA_IMPORTADO(_TMP)?\))", "", nome, flags=re.IGNORECASE).replace("..", ".").replace(" .", ".")

            # ... dentro do importar_xmls_em_lote (no lugar do bloco de renomeio) ...
            base_nome = limpar_sufixo(os.path.basename(caminho_xml))
            novo_nome = os.path.join(PASTA_LOCAL_XML, base_nome.replace(
                ".xml",
                "(JA_IMPORTADO_TMP).xml" if erro_já_importado else "(FEITO_TMP).xml"
            ))
            os.rename(caminho_xml, novo_nome)
            logging.info(f"Arquivo renomeado para: {novo_nome}")

            # ✅ marca coluna “XML IMPORTADA SGI” (D)
            try:
                tree = ET.parse(novo_nome)
                ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
                d_emis = tree.find(".//nfe:ide/nfe:dhEmi", ns).text[:10]
                data_emissao = dt.strptime(d_emis, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception as e:
                logging.warning(f"Não conseguiu extrair data de emissão da NF {numero_nf}: {e}")
                data_emissao = ""

            linha = _get_or_create_row(numero_nf, data_emissao)
            _update_cell(linha, COL["XML IMPORTADA SGI"], True)

            # ---------- status ----------
            status = "JÁ IMPORTADA" if erro_já_importado else "OK"
            nfs_importadas.append((numero_nf, status))   # ←- salva tupla
            time.sleep(2)

        except Exception as e:
            logging.error(f"Erro ao importar {arquivo}: {e}")
            driver.save_screenshot(f"erro_upload_{numero_nf}.png")
            nfs_importadas.append((numero_nf, "ERRO"))   # ←- falhou
            continue

    logging.info("✅ Todos os XMLs foram processados (importados ou já existiam).")
    return nfs_importadas


def safe_rename(src, dst, tentativas=5, delay=0.4):
    for tentativa in range(tentativas):
        try:
            os.rename(src, dst)
            return True
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(delay)
    return False


import re  # regex para NF

# ------------------------------------------------------------------
# VINCULAÇÃO
# ------------------------------------------------------------------
def codigos_equivalentes(ref, codigo_final):
    if ref == codigo_final:
        return True
    if ref.lstrip("0") == codigo_final.lstrip("0") and 0 < len(ref) - len(ref.lstrip("0")) <= 2:
        return True
    if codigo_final.lstrip("0") == ref.lstrip("0") and 0 < len(codigo_final) - len(codigo_final.lstrip("0")) <= 2:
        return True
    return False


def esperar_vinculo(linha):
    try:
        WebDriverWait(linha, 3).until(
            EC.presence_of_element_located(
                (By.XPATH, './/span[contains(@class,"vincular-desvincular-glyphicon-check")]')
            )
        )
    except Exception:
        pass


def vincular_produtos(driver) -> bool:
    """
    Tenta vincular itens com caneta vermelha.
    Retorna True se, ao final, não sobra NENHUM ícone 'edit' (vermelho).
    """
    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((
            By.XPATH,
            '//table[@id="lista_itens_importacao_xml_nfe"]'
            '//span[contains(@class,"vincular-desvincular-glyphicon-edit") or '
            '      contains(@class,"vincular-desvincular-glyphicon-check")]'
        ))
    )

    tabela  = driver.find_element(By.ID, "lista_itens_importacao_xml_nfe")
    linhas  = tabela.find_elements(By.XPATH, ".//tbody/tr[starts-with(@id,\'xml_nfe_\')]")

    for linha in linhas:
        # Já vinculado? (ícone ✓)
        if linha.find_elements(By.XPATH,
            './/span[contains(@class,"glyphicon-check")]'):
            continue

        # Ainda pendente → ícone ✏️
        icone_edit = linha.find_element(By.XPATH,
            './/span[contains(@class,"glyphicon-edit")]')

        prod_nome = linha.find_element(By.XPATH,
            './td[contains(@class,"coluna-produto")]').text.strip()
        ref = linha.find_element(By.XPATH,
            './td[@data-title="Referência Fornecedor"]').text.strip()
        cods = re.findall(r"\((\d+)\)", prod_nome)
        cod_final = cods[-1] if cods else ""

        if "*(Sugestão)" in prod_nome and ref and codigos_equivalentes(ref, cod_final):
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", icone_edit)
                time.sleep(0.15)
                icone_edit.click()
                esperar_vinculo(linha)      # aguarda virar ✓
                logging.info(f"✅ vinculado {ref}")
            except Exception as e:
                logging.warning(f"⚠️ falhou ao vincular {ref}: {e}")
        else:
            logging.warning(f"🔴 {ref or '---'} sem sugestão – ação humana necessária.")

    # Se restou QUALQUER ícone ✏️, devolve False
    pendentes = tabela.find_elements(By.XPATH,
        './/span[contains(@class,"glyphicon-edit")]')
    return len(pendentes) == 0



def importar_e_vincular(driver):
    pendentes = [f for f in os.listdir(PASTA_LOCAL_XML)
                 if f.lower().endswith("(feito_tmp).xml") or f.lower().endswith("(ja_importado_tmp).xml")]
    if not pendentes:
        return []

    nfs_status = []
    nfs = sorted({re.match(r"(\d+)", f).group(1) for f in pendentes})

    for nf in nfs:
        try:
            driver.get("https://smart.sgisistemas.com.br/importacoes_xml_nfe")
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    f'//tr[td[@data-title="Número NF-e"]/a[text()="{nf}"]]//a'))
            )
            driver.execute_script("arguments[0].click();", link)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "lista_itens_importacao_xml_nfe"))
            )

            ok = vincular_produtos(driver)          # ← agora devolve bool

            linha = _get_or_create_row(nf)
            if ok:
                _update_cell(linha, COL["XML VINCULADA SGI"], True)
                nfs_status.append((nf, "OK"))
            else:
                _update_cell(linha, COL["XML VINCULADA SGI"], False)
                nfs_status.append((nf, "ERRO"))

        except Exception as e:
            logging.warning(f"NF {nf}: erro inesperado – {e}")
            nfs_status.append((nf, "ERRO"))

    return nfs_status

# =========================================
# Sessão 6.0 – Gerar Entrada
# =========================================
# ---------- DESCONTO / ACRÉSCIMOS ----------
def verificar_se_tem_desconto(driver):
    tabela  = driver.find_element(By.ID, "tabela_de_produtos")
    linhas  = tabela.find_elements(By.XPATH, ".//tbody/tr")
    tem_desc = False
    for idx, ln in enumerate(linhas, start=1):
        desc_txt = ln.find_elements(By.TAG_NAME, "td")[9].text.strip()  # 10ª coluna
        try:
            desc_val = float(desc_txt.replace('.', '').replace(',', '.'))
        except:
            desc_val = 0
        if desc_val > 0:
            logging.info(f"[ITEM {idx}] desconto = {desc_val}")
            tem_desc = True
    if tem_desc:
        logging.info("⚠️ Nota de FEIRA / MOSTRUÁRIO (há desconto nos itens).")
    else:
        logging.info("Nota normal (sem desconto).")
    return tem_desc


def preencher_outros_acrescimos(driver, tem_desconto):
    val_txt = driver.find_element(By.ID, "valor_itens").get_attribute("value")
    valor_itens = float(val_txt.replace('.', '').replace(',', '.'))
    if tem_desconto:
        valor_acrescimos = valor_itens * 3
    else:
        valor_acrescimos = valor_itens
    campo = driver.find_element(By.ID, "campo_valor_outros_acrescimos")
    campo.clear()
    campo.send_keys(f"{valor_acrescimos:.2f}".replace('.', ','))
    logging.info(f"Campo Outros Acréscimos = {valor_acrescimos}")


def gerar_entrada(driver,nf):
    w=WebDriverWait(driver,20)
    driver.get("https://smart.sgisistemas.com.br/importacoes_xml_nfe")
    try:
        link_elem = w.until(EC.element_to_be_clickable((By.XPATH,f'//tr[td[@data-title="Número NF-e"]/a[text()="{nf}"]]//a')))
        link_elem.click()
    except Exception:
        logging.warning(f"NF {nf}: não encontrada na lista para geração de entrada.")
        return None
    w.until(EC.element_to_be_clickable((By.ID,"gerar_entrada"))).click()
    try:w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'button[data-bb-handler="confirm"]'))).click()
    except:pass
    w.until(lambda d:"/entrada?xml_nfe_id" in d.current_url)
    # quantidade por local (passa tudo pro CD =6)
    w.until(EC.presence_of_element_located((By.ID,"tabela_de_produtos")))
    # Preencher quantidades no modal
    wait = WebDriverWait(driver, 15)
    tabela = driver.find_element(By.ID, "tabela_de_produtos")
    linhas = tabela.find_elements(By.XPATH, ".//tbody/tr")
    for idx, linha in enumerate(linhas):
        print(f"\n[ITEM {idx+1}]")
        td_qtde = linha.find_element(By.XPATH, ".//td[contains(@class,'qtde-por-local-estocagem')]")
        try:
            td_qtde.click()
        except:
            driver.execute_script("arguments[0].click();", td_qtde)

        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@class,'modal-content')]//h4[contains(text(),'Quantidade por Local de Estocagem')]")
        ))

        tds = linha.find_elements(By.TAG_NAME, "td")
        print("Valores da linha:")
        for i, td in enumerate(tds):
            print(f"  Coluna {i}: {td.text.strip()}")

        qtd_nota = tds[4].text.strip()
        print(f"Qtde Nota coletada: [{qtd_nota}]")

        # Busca apenas o campo realmente visível e habilitado no modal
        inputs = driver.find_elements(By.XPATH, "//div[contains(@class,'modal-content')]//input[@data-local_id='6']")
        campo_cd = None
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                campo_cd = inp
                break

        if campo_cd:
            campo_cd.clear()
            campo_cd.send_keys(qtd_nota)
            print(f"Digitado '{qtd_nota}' no campo Depósito C.D.")
        else:
            print("ATENÇÃO: Não achou campo visível para Depósito C.D. no pop-up.")

        try:
            btn_concluir = driver.find_element(By.ID, "concluir_quantidade_por_local")
            btn_concluir.click()
        except Exception as e:
            print(f"ERRO ao clicar em concluir: {e}")

        wait.until(EC.invisibility_of_element_located(
            (By.XPATH, "//div[contains(@class,'modal-content')]//h4[contains(text(),'Quantidade por Local de Estocagem')]")
        ))
        time.sleep(0.5)


    tem_desc = verificar_se_tem_desconto(driver)
    preencher_outros_acrescimos(driver, tem_desc)
    # forma pagamento boleto
    Select(driver.find_element(By.ID,"forma_pagamento_id_0")).select_by_visible_text("Boleto")
    # salvar
    driver.find_element(By.ID,"botao_salvar_continuar").click()
    for _ in range(20):
        time.sleep(0.7)
        if "numero_lancamento=" in driver.current_url:
            return driver.current_url
    return None

def gerar_entradas(driver, nfs):
    ok=[]
    for nf in sorted(set(nfs)): # elimina duplicatas
        _garantir_sessao(driver)
        link=gerar_entrada(driver,nf)
        if link:
            linha=_get_or_create_row(nf); _update_cell(linha,COL["XML ENTRADA SALVA SGI"],"VERDADEIRO")
            _update_cell(linha,COL["LINK LANÇAMENTO SGI"],link)
            ok.append((nf,link))
        else:
            logging.error(f"NF {nf}: erro ao gerar entrada")
    return ok

# =========================================
# Sessão 7.0 – Boletos (VERSÃO ROBUSTA)
# =========================================
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import ElementNotInteractableException

# ---------- Utilidades ----------
def apagar_e_digitar(element, texto):
    """Garante que o campo esteja selecionável, apaga e digita novo valor."""
    try:
        WebDriverWait(element.parent, 5).until(lambda d: element.is_displayed() and element.is_enabled())
        element.click()
    except ElementNotInteractableException:
        element._parent.execute_script("arguments[0].click();", element)
    element.send_keys(Keys.CONTROL, 'a')
    time.sleep(0.1)
    element.send_keys(Keys.BACKSPACE)
    time.sleep(0.1)
    element.send_keys(str(texto))
    time.sleep(0.2)

def _celula_true(valor):
    return str(valor).strip().upper() in ("TRUE", "VERDADEIRO")

def autocomp(driver, campo_id, texto_digitado):
    """Autocomplete genérico – clica na primeira sugestão se existir, fallback seta-↓ + Enter."""
    el = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, campo_id)))
    el.clear()
    el.send_keys(texto_digitado)
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tt-suggestion")))
        driver.find_elements(By.CSS_SELECTOR, "div.tt-suggestion")[0].click()
    except Exception:
        el.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
    time.sleep(0.3)

def selecionar_autocomplete_exato(driver, campo_id, texto_digitado, texto_exato):
    """Seleciona exatamente a sugestão desejada (ex.: 'Pagamento de Fornecedor')."""
    el = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, campo_id)))
    el.clear()
    el.send_keys(texto_digitado)
    time.sleep(1.5)
    for sug in driver.find_elements(By.CSS_SELECTOR, "div.tt-suggestion"):
        if sug.text.strip().lower() == texto_exato.strip().lower():
            sug.click()
            time.sleep(0.3)
            return
    raise Exception(f"Sugestão '{texto_exato}' não encontrada em {campo_id}.")

# ---------- XML ----------
# ---------- XML ----------
def extrair_info_xml(xml_path):
    tree = ET.parse(xml_path)
    ns   = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    ide   = tree.find('.//nfe:infNFe/nfe:ide', ns)
    nf    = ide.find('nfe:nNF', ns).text
    data  = dt.strptime(ide.find('nfe:dhEmi', ns).text[:10],
                        "%Y-%m-%d").strftime("%d/%m/%Y")

    # ----- detecta desconto em QUALQUER item -----
    tem_desconto = any(
        float( (det.find('nfe:vDesc', ns).text or '0').replace(',', '.') ) > 0
        for det in tree.findall('.//nfe:det', ns)
        if det.find('nfe:vDesc', ns) is not None
    )
    fator = 3 if tem_desconto else 1

    # ----- duplicatas (já ajustadas) -----
    dups = []
    for d in tree.findall('.//nfe:dup', ns):
        valor = float(d.find('nfe:vDup', ns).text.replace(',', '.')) * fator
        dups.append({
            "nDup":  d.find('nfe:nDup', ns).text,
            "vDup":  f"{valor:.2f}",                 # string pt-BR depois
            "dVenc": dt.strptime(
                        d.find('nfe:dVenc', ns).text[:10],
                        "%Y-%m-%d").strftime("%d/%m/%Y")
        })

    # converte ponto→vírgula para o SGI
    for dup in dups:
        dup["vDup"] = dup["vDup"].replace('.', ',')

    return {"numero_nf": nf,
            "data_emissao": data,
            "duplicatas":   dups}

# ---------- Tabela de parcelas ----------
def preencher_parcelas(driver, duplicatas):
    tabela = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "tabela_vencimentos_titulo")))
    expected = len(duplicatas)
    for _ in range(20):
        if len(tabela.find_elements(By.XPATH, ".//tbody/tr")) >= expected:
            break
        time.sleep(0.5)
    else:
        raise Exception("Tabela de parcelas não carregou linhas suficientes.")
    # começa do segundo boleto
    for i, dup in enumerate(duplicatas[1:], start=1):
        linha = tabela.find_elements(By.XPATH, ".//tbody/tr")[i]

        cell_venc = linha.find_elements(By.TAG_NAME, "td")[1]
        ActionChains(driver).double_click(cell_venc).perform()
        campo_venc = WebDriverWait(cell_venc, 5).until(
            EC.element_to_be_clickable((By.XPATH, ".//input[contains(@id,'data_vencimento')]")))
        apagar_e_digitar(campo_venc, dup['dVenc'])

        cell_valor = linha.find_elements(By.TAG_NAME, "td")[-2]
        ActionChains(driver).double_click(cell_valor).perform()
        campo_valor = WebDriverWait(cell_valor, 5).until(
            EC.element_to_be_clickable((By.XPATH, ".//input[contains(@id,'valor_nominal')]")))
        apagar_e_digitar(campo_valor, dup['vDup'].replace('.', ','))

        # Complemento opcional
        try:
            cell_comp = linha.find_elements(By.TAG_NAME, "td")[4]
            ActionChains(driver).double_click(cell_comp).perform()
            campo_comp = WebDriverWait(cell_comp, 3).until(
                EC.element_to_be_clickable((By.XPATH, ".//input[contains(@id,'complemento')]")))
            apagar_e_digitar(campo_comp, "X")
        except Exception:
            pass

# ---------- Cadastro de Título ----------
def cadastrar_titulo(driver, info):
    driver.get("https://smart.sgisistemas.com.br/titulos/new")

    # Autocompletes principais
    autocomp(driver, "autocompletar_tipo_titulo_id", "Pagar")
    autocomp(driver, "autocompletar_pessoa_cliente_fornecedor_id", "MATIC INDUSTRIA DE MÓVEIS LTDA")
    Select(driver.find_element(By.ID, "conta_financeira_id")).select_by_value("2")
    driver.find_element(By.ID, "numero_titulo").send_keys(info["numero_nf"])
    driver.find_element(By.ID, "complemento").send_keys("X")
    autocomp(driver, "autocompletar_forma_pagamento_id", "Boleto *")
    autocomp(driver, "autocompletar_portador_titulo_id", "Carteira")
    selecionar_autocomplete_exato(driver, "autocompletar_historico_receita_despesa_id",
                                  "Pagamento de Fornecedor", "Pagamento de Fornecedor")

    # Datas e valores
    elem_data = driver.find_element(By.ID, "data_emissao"); elem_data.clear(); elem_data.send_keys(info["data_emissao"])
    valor_primeira = info["duplicatas"][1]['vDup'] if len(info["duplicatas"]) > 1 else info["duplicatas"][0]['vDup']
    elem_valor = driver.find_element(By.ID, "valor_cada_titulo"); elem_valor.clear(); elem_valor.send_keys(valor_primeira.replace('.', ','))
    elem_venc  = driver.find_element(By.ID, "primeira_data_vencimento"); elem_venc.clear(); elem_venc.send_keys(info["duplicatas"][0]["dVenc"])

    # Quantidade de parcelas – usa função robusta para evitar “13 parcelas”
    campo_parcelas = driver.find_element(By.ID, "quantidade_parcelas")
    apagar_e_digitar(campo_parcelas, str(len(info["duplicatas"])))
    campo_parcelas.send_keys(Keys.TAB)
    time.sleep(1.5)

    if len(info["duplicatas"]) > 1:
        preencher_parcelas(driver, info["duplicatas"])

    driver.find_element(By.XPATH, '//input[@type="submit" and @value="Salvar"]').click()
    time.sleep(1.5)
    # Retorna True se não há alerta de erro
    return not driver.find_elements(By.CSS_SELECTOR, '.alert-danger')

# ---------- Cadastro de boletos para lista de NFs ----------
def cadastrar_boletos(driver, lista_nf_link):
    boletos_ok = []
    for nf, _ in lista_nf_link:
        linha = _get_or_create_row(nf)
        valor_boleto = _read_cell(linha, COL["XML BOLETO SALVO SGI"], default="")
        if _celula_true(valor_boleto):
            continue
        possiveis = [f for f in os.listdir(PASTA_LOCAL_XML)
             if f.startswith(nf) and f.lower().endswith('.xml')
             and ('feito' in f.lower() or 'ja_importado' in f.lower())]
        xml_path = os.path.join(PASTA_LOCAL_XML, possiveis[0]) if possiveis else None
        if not xml_path:
            logging.warning(f"XML {nf} não encontrado para boleto"); continue

        info = extrair_info_xml(xml_path)
        _garantir_sessao(driver)
        tentativas, sucesso = 0, False
        while tentativas < 3 and not sucesso:
            try:
                sucesso = cadastrar_titulo(driver, info)
                if not sucesso:
                    logging.error(f"NF {nf} – erro ao salvar (alerta na página).")
                else:
                    _update_cell(linha, COL["XML BOLETO SALVO SGI"], "VERDADEIRO")
                    boletos_ok.append(nf)
            except Exception as e:
                logging.error(f"NF {nf} – erro inesperado: {e}")
                driver.refresh()
            tentativas += 1
        if not sucesso:
            logging.error(f"NF {nf} – falhou após 3 tentativas.")
    return boletos_ok
    
# ---------- Wrapper: cadastra boletos para QUALQUER lista de NFs importadas ----------
def cadastrar_boletos_para_nfs(driver, nfs_importadas):
    """
    Recebe uma lista de números de NF (strings) e cadastra os boletos
    para cada uma, usando o XML da pasta local (FEITO_TMP/JA_IMPORTADO_TMP também serve).
    Reaproveita a função cadastrar_boletos existente.
    """
    # elimina duplicatas e transforma em tuplas (nf, None) para compatibilidade
    lista = [(nf, None) for nf in sorted(set(nfs_importadas))]
    return cadastrar_boletos(driver, lista)

# =========================================
# Sessão 8.0 – Renomear XMLs e Drive
# =========================================
def renomear_xmls():
    for f in glob.glob(os.path.join(PASTA_LOCAL_XML, "*(FEITO_TMP).xml")) \
            + glob.glob(os.path.join(PASTA_LOCAL_XML, "*(JA_IMPORTADO_TMP).xml")):
        os.rename(f, f.replace("(FEITO_TMP)", "(FEITO)").replace("(JA_IMPORTADO_TMP)", "(FEITO)"))

    from app.google_sheets_auth import load_sa_credentials
    creds_drive=load_sa_credentials(["https://www.googleapis.com/auth/drive"])
    drive=build("drive","v3",credentials=creds_drive, cache_discovery=False)
    for f in drive.files().list(q=f"'{ID_PASTA_GOOGLE_DRIVE}' in parents and trashed=false and name contains '(FEITO_TMP)'",
                                fields="files(id,name)").execute().get("files",[]):
        novo = f["name"].replace("(FEITO_TMP)","(FEITO)")
        drive.files().update(fileId=f["id"],body={'name':novo}).execute()

# =========================================
# Sessão 8.1 – Renomear também no Google Drive
# =========================================
def renomear_feitos_no_drive():
    """
    Procura no Drive o XML original e o renomeia para (FEITO).xml
    usando o mesmo nome já renomeado localmente.
    """
    from app.google_sheets_auth import load_sa_credentials
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds  = load_sa_credentials(SCOPES)
    drive  = build('drive', 'v3', credentials=creds, cache_discovery=False)

    arquivos_feitos = [
        f for f in os.listdir(PASTA_LOCAL_XML)
        if f.lower().endswith('(feito).xml')
    ]
    for nome_feito in arquivos_feitos:
        nome_original     = nome_feito.replace('(FEITO)', '').strip()
        nome_novo_drive   = nome_feito
        query = (
            f"'{ID_PASTA_GOOGLE_DRIVE}' in parents and trashed=false "
            f"and name = '{nome_original}'"
        )
        files = drive.files().list(q=query, fields="files(id,name)").execute().get('files', [])
        if files:
            drive.files().update(
                fileId=files[0]['id'],
                body={'name': nome_novo_drive}
            ).execute()
            logging.info(f"Drive: {nome_original} → {nome_novo_drive}")
        else:
            logging.info(f"Drive: {nome_original} já renomeado ou não encontrado.")


# =========================================
# Sessão 9.0 – Notificar WhatsApp 
# =========================================
def enviar_whatsapp_texto(mensagem, chrome_user_dir):
    """
    Envia 'mensagem' para o grupo AVISOS/GRUPO - POS VENDA no WhatsApp Web,
    usando o perfil persistente do Chrome (chrome_user_dir).
    Mantém o loop de verificação “Carregando conversas…” e screenshot de erro.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    import time

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={chrome_user_dir}")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://web.whatsapp.com/")
        logging.info("Aguardando WhatsApp Web carregar (escaneie o QR se necessário)…")

        tentativas, carregou = 0, False
        while tentativas < 50:         # 50 × 10 s = ~8 min
            time.sleep(10)
            tentativas += 1
            try:
                driver.find_element(By.XPATH, '//div[@role="textbox" and @contenteditable="true"]')
                carregou = True
                logging.info("WhatsApp Web carregado!")
                break
            except:
                try:
                    driver.find_element(By.XPATH, "//*[contains(text(),'Carregando conversas')]")
                    logging.info(f"Tentativa {tentativas}: ainda carregando conversas…")
                except:
                    logging.info(f"Tentativa {tentativas}: aguardando interface…")

        if not carregou:
            logging.error("WhatsApp não carregou a tempo.")
            driver.save_screenshot("erro_whatsapp_loading.png")
            return

        # -------- procurar o grupo --------
        caixa_pesq = driver.find_element(By.XPATH, '//div[@role="textbox" and @contenteditable="true"]')
        caixa_pesq.clear()
        caixa_pesq.click()
        time.sleep(1)
        caixa_pesq.send_keys("AVISOS/GRUPO - POS VENDA")
        time.sleep(2)
        caixa_pesq.send_keys(Keys.ENTER)
        time.sleep(2)

        # -------- enviar a mensagem --------
        caixa_msg = driver.find_element(By.XPATH, '//footer//div[@contenteditable="true"]')
        caixa_msg.click()
        for linha in mensagem.strip().splitlines():
            caixa_msg.send_keys(linha)
            caixa_msg.send_keys(Keys.SHIFT, Keys.ENTER)
        caixa_msg.send_keys(Keys.ENTER)

        logging.info("Mensagem de relatório enviada com sucesso.")
        time.sleep(2)

    except Exception as e:
        logging.error(f"Erro ao enviar mensagem no WhatsApp: {e}")
        driver.save_screenshot("erro_whatsapp.png")
    finally:
        driver.quit()


# =========================================
# Sessão 10.0 – Fluxo principal (COMPLETO E AJUSTADO)
# =========================================
LOCK_PATH = "/app/.baixas_encomendas.lock"

def _acquire_lock():
    if os.path.exists(LOCK_PATH):
        # lock antigo? se passou de 2h, descarta
        try:
            if (time.time() - os.path.getmtime(LOCK_PATH)) > 7200:
                os.remove(LOCK_PATH)
        except Exception:
            pass
    if os.path.exists(LOCK_PATH):
        logging.info("⛔ Já existe uma execução em andamento. Encerrando.")
        return False
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True

def _release_lock():
    try:
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
    except Exception:
        pass

def main():
    logging.info("🚀 main() — INÍCIO")
    if not _acquire_lock():
        return
    
    try:
        baixar_xmls_drive()

        # 1) Existe algo pra processar?
        arquivos = [
            a for a in os.listdir(PASTA_LOCAL_XML)
            if a.lower().endswith(".xml")
            and "(feito" not in a.lower()
            and "(ja_importado" not in a.lower()
        ]
        if not arquivos:
            logging.info("Nenhum XML pendente para processar. Encerrando script.")
            return

        driver = novo_driver()
        rel = {etapa: [] for etapa in
               ("IMPORTAR XML", "VINCULAR PRODUTOS", "GERAR ENTRADA", "GERAR BOLETO")}
        texto = ""

        # placeholders p/ não dar NameError no relatório
        nfs_imp = []
        nfs_vinc = []
        entradas_ok = []
        boletos_ok = []

        try:
            login(driver)

            # 3) IMPORTAR TODOS OS XMLs
            nfs_imp = importar_xmls_em_lote(driver, arquivos)   # list[(nf, status)]

            # 4) VINCULAR (best effort)
            nfs_vinc = importar_e_vincular(driver)              # list[(nf, "OK"|"ERRO")]

            # 5) GERAR ENTRADA (somente nas que vincularam OK)
            try:
                entradas_ok = gerar_entradas(driver, [nf for nf, st in nfs_vinc if st == "OK"])  # list[(nf, link)]
            except Exception:
                logging.exception("Erro ao gerar entradas; prosseguindo mesmo assim para boletos.")

        finally:
            # 6) BOLETOS (SEMPRE) – para TODAS as NFs importadas, mesmo com erros anteriores
            try:
                nfs_para_boleto = [nf for nf, _st in nfs_imp] if nfs_imp else []
                if nfs_para_boleto:
                    boletos_ok = cadastrar_boletos_para_nfs(driver, nfs_para_boleto)  # list[nf]
            except Exception:
                logging.exception("Erro ao cadastrar boletos (bloco finally).")

            # ======= Montagem do relatório =======
            try:
                cabecalho = "*MATIC - ENTRADA DE XML FINALIZADA*\n"

                # Importação
                for _nf, *status in nfs_imp:
                    rel["IMPORTAR XML"].append(f"- {_nf} {status[0] if status else 'OK'}")

                # Vincular
                for _nf, st in nfs_vinc:
                    rel["VINCULAR PRODUTOS"].append(f"- {_nf} {st}")

                # Entrada
                nfs_que_viraram_entrada = {nf for nf, _link in entradas_ok}
                for _nf, _link in entradas_ok:
                    rel["GERAR ENTRADA"].append(f"- {_nf} OK ({_link})")
                for _nf, st in nfs_vinc:
                    if st == "OK" and _nf not in nfs_que_viraram_entrada:
                        rel["GERAR ENTRADA"].append(f"- {_nf} ERRO")

                # Boletos
                for _nf in boletos_ok:
                    rel["GERAR BOLETO"].append(f"- {_nf} OK")
                for _nf in (set([nf for nf, _ in nfs_imp]) - set(boletos_ok)):
                    rel["GERAR BOLETO"].append(f"- {_nf} ERRO")

                houve_atividade = any(rel[etapa] for etapa in rel)
                if houve_atividade:
                    texto = cabecalho + "\n\n" + "\n\n".join(
                        f"*{etapa}*\n" + "\n".join(rel[etapa])
                        for etapa in ("IMPORTAR XML", "VINCULAR PRODUTOS", "GERAR ENTRADA", "GERAR BOLETO")
                        if rel[etapa]
                    )
            finally:
                # encerra e rotinas finais
                try:
                    # Limpar perfil único do Chrome
                    prof = getattr(driver, "_lebebe_profile_dir", None)
                    if prof and os.path.isdir(prof):
                        import shutil
                        shutil.rmtree(prof, ignore_errors=True)
                    driver.quit()
                except Exception:
                    pass

                renomear_xmls()
                renomear_feitos_no_drive()

                # WhatsApp notification disabled in container mode
                # (requires persistent Chrome profile and QR scan)
                if texto.strip():
                    logging.info("Relatório gerado (WhatsApp desabilitado em container):")
                    logging.info(texto.strip())

        logging.info("Processo COMPLETO concluído!")
    
    finally:
        _release_lock()
        logging.info("✅ main() — FIM")

def _selftest_ping():
    try:
        logging.info("🩺 SELFTEST: iniciando ping")
        # grava um carimbo na planilha (linha 1, col J)
        SHEETS.values().update(
            spreadsheetId=PLANILHA_ID,
            range=f"'{ABA_CONTROLE}'!J1",
            valueInputOption="RAW",
            body={"values":[[dt.now().strftime("%d/%m/%Y %H:%M:%S")]]}
        ).execute()
        logging.info("🩺 SELFTEST: Sheets OK")
        # cria log “vivo”
        logging.info("🩺 SELFTEST: fim (OK)")
    except Exception:
        logging.exception("🩺 SELFTEST: falhou")

# =========================================
# Sessão 99.0 – Entry point (fora da função main)
# =========================================
if __name__ == "__main__":
    logging.getLogger("googleapiclient.discovery").setLevel(logging.ERROR)
    logging.info("==== Iniciando matic_fluxo_integrado ====")
    try:
        _selftest_ping()  # <- rode o ping primeiro
        main()
    except Exception:
        logging.exception("Falha na execução principal.")
