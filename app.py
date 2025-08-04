import re
import time
import os
import sys
import json
import logging
from contextlib import redirect_stderr
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuración de selectores por dominio (tu configuración original)
DOMAIN_CONFIG = {
    'aristeguinoticias.com': {
        'title_selector': ['h1.entry-title', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div.entry-content',
        'body_fallback_selector': 'div.contenido',
        'wait_time': 20
    },
    'www.infobae.com': {
        'title_selector': ['h1.article-headline', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div.body-article p.paragraph[data-mrf-recirculation="Links inline"]'
    },
    'www.eluniversal.com.mx': {
        'title_selector': ['h1.title', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div.colum2 p.sc__font-paragraph[itemprop="description"]',
        'body_fallback_selector': 'p.sc__font-paragraph[itemprop="description"]'
    },
    'lopezdoriga.com': {
        'title_selector': ['h1.entry-title', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div.article-content'
    },
    'www.milenio.com': {
        'title_selector': ['h1.title', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div#content-body.media-container.news[itemprop="articleBody"]'
    },
    'www.elfinanciero.com.mx': {
        'title_selector': ['h1.c-heading.b-headline', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'article.b-article-body.article-body-wrapper'
    },
    'www.jornada.com.mx': {
        'title_selector': ['h1.titulo_art', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title', 'h1'],
        'body_selector': 'div#content_nitf'
    },
    'www.excelsior.com.mx': {
        'title_selector': ['h1', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title'],
        'body_selector': 'div.field-items'
    },
    'www.eleconomista.com.mx': {
        'title_selector': ['h1', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title'],
        'body_selector': 'div.c-detail__body'
    },
    'www.proceso.com.mx': {
        'title_selector': ['h1.titular'],
        'body_selector': 'div.cuerpo-nota#cuerpo-nota'
    },
    'www.sinembargo.mx': {
        'title_selector': ['h1', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title'],
        'body_selector': 'div.entry-content'
    },
    'lasillarota.com': {
        'title_selector': ['h1.titulo'],
        'body_selector': 'div.article-content--cuerpo'
    },
    'www.debate.com.mx': {
        'title_selector': ['h1.newsfull__title'],
        'body_selector': 'div.newsfull__body'
    },
    'default': {
        'title_selector': ['h1', 'h1.title', 'h1.post-title', 'h1.entry-title', 'meta[property="og:title"]', 'meta[name="title"]', 'title'],
        'body_selector': 'article, div.entry-content, div.post-content, div.content, div.article-body, main, div[itemprop="articleBody"]'
    }
}

def get_domain(url):
    """Extrae el dominio de la URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc

def setup_chrome_driver():
    """Configurar Chrome driver para ambiente Linux (Render)"""
    options = Options()
    
    # Configuraciones para ambiente headless en Render
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-login-animations')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-default-apps')
    options.add_argument('--hide-scrollbars')
    options.add_argument('--enable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--output=/dev/null')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36')
    
    # Configuraciones adicionales para Render
    options.add_argument('--single-process')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-ipc-flooding-protection')
    
    # Configurar servicio
    # En Render, ChromeDriver estará disponible globalmente
    service = Service()  # Sin especificar ruta, usa el del PATH
    
    return webdriver.Chrome(service=service, options=options)

def get_news_content(url, max_retries=2):
    driver = None
    try:
        for attempt in range(max_retries):
            try:
                logging.info(f"Intento {attempt + 1} para procesar: {url}")
                
                # Configurar driver
                driver = setup_chrome_driver()
                driver.set_page_load_timeout(60)
                driver.get(url)
                
                # Obtener el dominio para configuraciones específicas
                domain = get_domain(url)
                config = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG['default'])
                
                # Espera dinámica para aristeguinoticias.com
                if domain == 'aristeguinoticias.com':
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, config['body_selector']))
                        )
                    except TimeoutException:
                        logging.warning(f"Timeout en WebDriverWait para {url}, usando espera fija")
                        time.sleep(config.get('wait_time', 15))
                else:
                    time.sleep(15)
                
                # Obtener el HTML renderizado
                html = driver.page_source
                
                # Parsear con BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Eliminar scripts, estilos, comentarios y elementos no deseados
                for element in soup(['script', 'style', 'comment', 'nav', 'footer', 'aside', 'iframe']):
                    element.decompose()
                
                # Extraer el título
                title = None
                for selector in config['title_selector']:
                    try:
                        if selector.startswith('meta'):
                            element = soup.select_one(selector)
                            if element and element.get('content'):
                                title = element.get('content')
                                break
                        elif selector == 'title':
                            element = soup.find('title')
                            if element and element.get_text(strip=True):
                                title = element.get_text(strip=True)
                                break
                        else:
                            element = soup.select_one(selector)
                            if element and element.get_text(strip=True):
                                title = element.get_text(strip=True)
                                break
                    except Exception:
                        continue
                
                if not title:
                    title = "Título no encontrado"
                
                # Extraer el cuerpo (tu lógica original)
                try:
                    if domain == 'www.excelsior.com.mx':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            body_text = content_div.get_text(strip=True)
                        else:
                            body_text = None
                    elif domain == 'www.eleconomista.com.mx':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            body_text = content_div.get_text(strip=True)
                        else:
                            body_text = None
                    elif domain == 'www.proceso.com.mx':
                        bajada = soup.select_one('strong.bajada')
                        bajada_text = bajada.get_text(strip=True) if bajada else ''
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            for aside in content_div.select('aside.relacionadas.con-foto.linea-1078'):
                                aside.decompose()
                            cuerpo_text = content_div.get_text(strip=True)
                            body_text = f"{bajada_text} {cuerpo_text}".strip() if bajada_text else cuerpo_text
                        else:
                            body_text = bajada_text if bajada_text else None
                    elif domain == 'www.sinembargo.mx':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            for figure in content_div.select('figure'):
                                figure.decompose()
                            body_text = content_div.get_text(strip=True)
                        else:
                            body_text = None
                    elif domain == 'aristeguinoticias.com':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            body_text = content_div.get_text(strip=True)
                        else:
                            content_div = soup.select_one(config.get('body_fallback_selector', ''))
                            if content_div:
                                for unwanted in content_div.select('div.ad, div.share, div.comments, div.related-posts, div.social, div.tags, p.author, div.meta'):
                                    unwanted.decompose()
                                body_text = content_div.get_text(strip=True)
                            else:
                                body_text = None
                    elif domain == 'lasillarota.com':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            for unwanted in content_div.select('div.container, p.image-align-center, strong, div.tags-cloud, a[href="https://www.whatsapp.com/channel/0029Va6evSkGk1Ftej78ks0B"], a[href="https://news.google.com/publications/CAAqKggKIiRDQklTRlFnTWFoRUtEMnhoYzJsc2JHRnliM1JoTG1OdmJTZ0FQAQ?hl=es-419&gl=MX&ceid=MX%3Aes-419"]'):
                                unwanted.decompose()
                            body_text = content_div.get_text(strip=True)
                        else:
                            body_text = None
                    elif domain == 'www.debate.com.mx':
                        content_div = soup.select_one(config['body_selector'])
                        if content_div:
                            for unwanted in content_div.select('div.ck-related-news, li'):
                                unwanted.decompose()
                            body_text = content_div.get_text(strip=True)
                        else:
                            body_text = None
                    elif domain in ['www.infobae.com', 'www.eluniversal.com.mx']:
                        paragraphs = soup.select(config['body_selector'])
                        if paragraphs:
                            body_text = ' '.join(p.get_text(strip=True) for p in paragraphs)
                        else:
                            body_text = None
                        if not body_text and domain == 'www.eluniversal.com.mx':
                            paragraphs = soup.select(config.get('body_fallback_selector', ''))
                            if paragraphs:
                                body_text = ' '.join(p.get_text(strip=True) for p in paragraphs)
                            else:
                                body_text = None
                    else:
                        article = soup.select_one(config['body_selector'])
                        if article:
                            for unwanted in article.select('div.ad, div.share, div.comments, div.related-posts, div.social, div.tags, p.author, div.meta, div.sharedaddy, div.entry-meta, figure, aside, iframe'):
                                unwanted.decompose()
                            body_text = article.get_text(separator=' ', strip=True)
                        else:
                            body_text = None
                    
                    if not body_text and domain == 'aristeguinoticias.com':
                        article = soup.select_one('div.contenido')
                        if article:
                            for unwanted in article.select('div.ad, div.share, div.comments, div.related-posts, div.social, div.tags, p.author, div.meta, div.sharedaddy, div.entry-meta'):
                                unwanted.decompose()
                            body_text = article.get_text(separator=' ', strip=True)
                    
                    if not body_text and domain not in ['www.infobae.com', 'www.eluniversal.com.mx', 'aristeguinoticias.com', 'lopezdoriga.com', 'www.milenio.com', 'www.elfinanciero.com.mx', 'www.jornada.com.mx', 'www.excelsior.com.mx', 'www.eleconomista.com.mx', 'www.proceso.com.mx', 'www.sinembargo.mx', 'lasillarota.com', 'www.debate.com.mx']:
                        article = soup.select_one('article') or soup.body
                        if article:
                            for unwanted in article.select('div.ad, div.share, div.comments, div.related-posts, div.social, div.tags, p.author, div.meta, div.sharedaddy, div.entry-meta'):
                                unwanted.decompose()
                            body_text = article.get_text(separator=' ', strip=True)
                    
                    if not body_text:
                        body_text = f"No se pudo encontrar el cuerpo de la noticia para el selector {config['body_selector']}."
                
                except Exception as e:
                    body_text = f"Error al extraer el cuerpo: {str(e)}"
                
                # Limpiar texto: eliminar espacios múltiples y líneas vacías
                body_text = re.sub(r'\s+', ' ', body_text).strip()
                
                # Limitar longitud para evitar contenido irrelevante
                max_length = 5000
                if len(body_text) > max_length:
                    body_text = body_text[:max_length] + '...'
                
                logging.info(f"Extracción exitosa para: {url}")
                return title, body_text
            
            except (WebDriverException, TimeoutException) as e:
                logging.error(f"Intento {attempt + 1} fallido para {url}: {str(e)}")
                if attempt < max_retries - 1:
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    time.sleep(2)
                    continue
                return "Error", f"Error de Selenium al procesar la noticia tras {max_retries} intentos: {str(e)}"
    
    except Exception as e:
        logging.error(f"Error general al procesar {url}: {str(e)}")
        return "Error", f"Error general al procesar la noticia: {str(e)}"
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

# Rutas de la API Flask
@app.route('/', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        "status": "ok",
        "message": "News Scraper API is running",
        "version": "1.0.0"
    })

@app.route('/scrape', methods=['POST'])
def scrape_news():
    """Endpoint principal para scraping de noticias"""
    try:
        # Obtener datos del request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se proporcionaron datos JSON"}), 400
        
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL requerida"}), 400
        
        # Validar y normalizar URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        logging.info(f"Procesando solicitud para: {url}")
        
        # Ejecutar el scraping
        title, body = get_news_content(url)
        
        # Construir respuesta
        result = {
            "success": True,
            "data": {
                "title": title,
                "body": body,
                "url": url,
                "domain": get_domain(url)
            },
            "timestamp": time.time()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error en endpoint /scrape: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/batch-scrape', methods=['POST'])
def batch_scrape():
    """Endpoint para procesar múltiples URLs"""
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data:
            return jsonify({"error": "Lista de URLs requerida"}), 400
        
        urls = data.get('urls', [])
        
        if not isinstance(urls, list):
            return jsonify({"error": "URLs debe ser una lista"}), 400
        
        if len(urls) > 10:  # Limitar a 10 URLs por request
            return jsonify({"error": "Máximo 10 URLs por request"}), 400
        
        results = []
        
        for url in urls:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            title, body = get_news_content(url)
            
            results.append({
                "url": url,
                "title": title,
                "body": body,
                "domain": get_domain(url)
            })
        
        return jsonify({
            "success": True,
            "data": results,
            "count": len(results),
            "timestamp": time.time()
        })
        
    except Exception as e:
        logging.error(f"Error en endpoint /batch-scrape: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
