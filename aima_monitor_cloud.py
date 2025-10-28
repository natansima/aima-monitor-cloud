#!/usr/bin/env python3
"""
Script de Monitoramento Automatizado da AIMA - VERSÃO CLOUD
"""

import asyncio
import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from playwright.async_api import async_playwright

# Configurações
AIMA_EMAIL = os.getenv("AIMA_EMAIL")
AIMA_PASSWORD = os.getenv("AIMA_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
STATUS_FILE = os.getenv("STATUS_FILE", "/app/data/aima_last_status.json")
AIMA_LOGIN_URL = "https://services.aima.gov.pt/CPLP/login.php"
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
RUN_HEADLESS = os.getenv("RUN_HEADLESS", "True").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

def validate_config():
    required_vars = {
        "AIMA_EMAIL": AIMA_EMAIL,
        "AIMA_PASSWORD": AIMA_PASSWORD,
        "SENDER_EMAIL": SENDER_EMAIL,
        "SENDER_PASSWORD": SENDER_PASSWORD,
        "RECEIVER_EMAIL": RECEIVER_EMAIL
    }
    missing = [var for var, val in required_vars.items() if not val]
    if missing:
        print("❌ ERRO: Variáveis de ambiente faltando:")
        for var in missing:
            print(f"   - {var}")
        return False
    return True

def load_last_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('status', '')
        except Exception as e:
            print(f"Erro ao carregar status anterior: {e}")
    return None

def save_status(status):
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'status': status,
                'timestamp': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f"✓ Status salvo em: {STATUS_FILE}")
    except Exception as e:
        print(f"✗ Erro ao salvar status: {e}")

def send_email_notification(subject, body, old_status, new_status):
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #d9534f;">⚠️ ATENÇÃO: Status do Processo AIMA Atualizado!</h2>
            <p>O status do seu processo na AIMA foi alterado em <strong>{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</strong>.</p>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <h3>Status Anterior:</h3>
            <div style="background-color: #f5f5f5; padding: 10px; border-left: 4px solid #5cb85c; margin-bottom: 15px;">
                <p><strong>{old_status if old_status else 'Desconhecido'}</strong></p>
            </div>
            <h3>Novo Status:</h3>
            <div style="background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                <p><strong>{new_status}</strong></p>
            </div>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <p>Por favor, acesse a página da AIMA para mais detalhes.</p>
            <p><a href="https://services.aima.gov.pt/CPLP/login.php">Acessar AIMA</a></p>
        </body>
    </html>
    """
    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print(f"✓ E-mail enviado para {RECEIVER_EMAIL}")
        return True
    except Exception as e:
        print(f"✗ Erro ao enviar e-mail: {e}")
        return False

async def extract_status_from_page(page):
    try:
        await page.wait_for_load_state('networkidle', timeout=15000)
        await asyncio.sleep(2)
        page_text = await page.evaluate('() => document.body.innerText')
        if "Estado do Processo" in page_text:
            lines = page_text.split('\n')
            for i, line in enumerate(lines):
                if "Estado do Processo" in line:
                    if len(line.strip()) > len("Estado do Processo"):
                        status_text = line.replace("Estado do Processo", "").strip()
                        if status_text:
                            return status_text
                    for j in range(i+1, min(i+5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith('Estado'):
                            if len(next_line) > 10:
                                return next_line
        return None
    except Exception as e:
        print(f"Erro ao extrair status: {e}")
        return None

async def check_status_once():
    print(f"\n{'='*70}")
    print(f"Verificação em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")
    print('='*70)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=RUN_HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            print("→ Acessando AIMA...")
            await page.goto(AIMA_LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            print("→ Fazendo login...")
            await page.fill("input[name='email']", AIMA_EMAIL)
            await page.fill("input[name='password']", AIMA_PASSWORD)
            async with page.expect_navigation(timeout=30000):
                await page.click("button[type='submit']")
            await asyncio.sleep(3)
            print("→ Verificando status...")
            current_status = await extract_status_from_page(page)
            if current_status:
                print(f"✓ Status: {current_status}")
                last_status = load_last_status()
                if last_status and last_status != current_status:
                    print("\n🚨 MUDANÇA DE STATUS DETECTADA!")
                    print(f"   Anterior: {last_status}")
                    print(f"   Atual: {current_status}\n")
                    send_email_notification(
                        subject="🚨 Status AIMA Atualizado!",
                        body="Status alterado",
                        old_status=last_status,
                        new_status=current_status
                    )
                elif not last_status:
                    print("✓ Primeira verificação. Status salvo.")
                else:
                    print("✓ Sem mudanças.")
                save_status(current_status)
                return True
            else:
                print("✗ Não foi possível extrair o status.")
                return False
        except Exception as e:
            print(f"✗ Erro: {e}")
            return False
        finally:
            await browser.close()

async def monitor_loop():
    print("\n" + "="*70)
    print("🔍 MONITOR AUTOMÁTICO DA AIMA - MODO CLOUD")
    print("="*70)
    print(f"Intervalo: {CHECK_INTERVAL_MINUTES} minutos")
    print(f"Headless: {'Sim' if RUN_HEADLESS else 'Não'}")
    print("="*70 + "\n")
    check_count = 0
    while True:
        try:
            check_count += 1
            print(f"\n{'─'*70}")
            print(f"Verificação #{check_count}")
            print(f"{'─'*70}")
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                if attempt > 1:
                    print(f"⟳ Tentativa {attempt}/{MAX_RETRIES}...")
                success = await check_status_once()
                if success:
                    break
                elif attempt < MAX_RETRIES:
                    await asyncio.sleep(30)
            if not success:
                print(f"✗ Falha após {MAX_RETRIES} tentativas.")
            next_check = datetime.now() + timedelta(minutes=CHECK_INTERVAL_MINUTES)
            print(f"\n⏰ Próxima verificação: {next_check.strftime('%d/%m/%Y às %H:%M:%S')}")
            await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            print("\n⛔ Interrompido")
            break
        except Exception as e:
            print(f"\n✗ Erro: {e}")
            await asyncio.sleep(300)

if __name__ == "__main__":
    print("\n🚀 Iniciando Monitor AIMA...\n")
    if not validate_config():
        exit(1)
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        print("\n✓ Finalizado.")
