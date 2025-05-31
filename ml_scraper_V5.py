import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import urllib.error
import re
import csv
import time
import random
import ssl
import json
import io
import statistics
from datetime import datetime
from collections import defaultdict, Counter

# Configuración de la página
st.set_page_config(
    page_title="MercadoLibre Scraper & Análisis",
    page_icon="🛒",
    layout="wide"
)

class MercadoLibreScraper:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
    
    def get_user_agent(self):
        return random.choice(self.user_agents)
    
    def fetch_url(self, url):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        headers = {
            'User-Agent': self.get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'es-ES,es;q=0.9',
        }
        
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            st.error(f"Error al acceder a {url}: {e}")
            return None
    
    def extract_json_data(self, html_content):
        if not html_content:
            return []
        
        json_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
        if not json_match:
            json_match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
            if not json_match:
                return []
        
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            return []
    
    def process_product_data(self, json_data):
        products_list = []
        
        if isinstance(json_data, dict) and "@graph" in json_data:
            for item in json_data["@graph"]:
                if item.get("@type") == "Product":
                    try:
                        product = {
                            'nombre': item.get("name", "No disponible"),
                            'estrellas': str(item.get("aggregateRating", {}).get("ratingValue", 0)),
                            'calificaciones': str(item.get("aggregateRating", {}).get("ratingCount", 0)),
                            'precio': str(item.get("offers", {}).get("price", "Precio no disponible")),
                            'descuento': "Sin descuento",
                            'envio': "Verificar en sitio",
                            'url': ""
                        }
                        
                        if "offers" in item and "url" in item["offers"]:
                            full_url = item["offers"]["url"]
                            clean_url = re.search(r'(https://[^#?]*)', full_url)
                            product['url'] = clean_url.group(1) if clean_url else full_url
                        
                        products_list.append(product)
                    except Exception as e:
                        st.warning(f"Error al procesar un producto: {e}")
        
        return products_list
    
    def extract_traditional_way(self, html_content):
        products_list = []
        
        if not html_content:
            return products_list
        
        product_patterns = [
            r'<div[^>]*class="[^"]*ui-search-result[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>\s*</div>',
            r'<li[^>]*class="[^"]*ui-search-layout__item[^"]*"[^>]*>.*?</li>'
        ]
        
        product_blocks = []
        for pattern in product_patterns:
            blocks = re.findall(pattern, html_content, re.DOTALL)
            if len(blocks) >= 5:
                product_blocks = blocks
                break
        
        for block in product_blocks:
            try:
                # URL del producto
                url_patterns = [
                    r'<a[^>]*href="(https://[^"]*?/p/[^"#]*)[#"]',
                    r'<a[^>]*href="(https://articulo\.mercadolibre\.[^/]*/[^"#]*)[#"]'
                ]
                product_url = ""
                for pattern in url_patterns:
                    url_match = re.search(pattern, block)
                    if url_match:
                        product_url = url_match.group(1).strip()
                        break
                
                # Nombre del producto
                title_patterns = [
                    r'<a[^>]*class="[^"]*poly-component__title[^"]*"[^>]*>(.*?)</a>',
                    r'<h2[^>]*class="[^"]*ui-search-item__title[^"]*"[^>]*>(.*?)</h2>'
                ]
                title = "Nombre no disponible"
                for pattern in title_patterns:
                    title_match = re.search(pattern, block, re.DOTALL)
                    if title_match:
                        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                        break
                
                # Precio
                price_patterns = [
                    r'<meta[^>]*itemprop="price"[^>]*content="(\d+)"',
                    r'<span[^>]*class="[^"]*price-tag-fraction[^"]*"[^>]*>(.*?)</span>'
                ]
                price = "0"
                for pattern in price_patterns:
                    price_match = re.search(pattern, block)
                    if price_match:
                        price = re.sub(r'[^\d.]', '', price_match.group(1).strip())
                        break
                
                # Estrellas
                stars = "0"
                stars_match = re.search(r'<p[^>]*class="[^"]*ui-review-capability__rating__average[^"]*"[^>]*>(.*?)</p>', block)
                if stars_match:
                    stars = stars_match.group(1).replace(',', '.').strip()
                
                # Número de calificaciones
                ratings_count = "0"
                ratings_match = re.search(r'<p[^>]*class="[^"]*ui-review-capability__rating__label[^"]*"[^>]*>([^<]*?)calificaciones</p>', block)
                if ratings_match:
                    ratings_text = ratings_match.group(1).strip()
                    ratings_val = re.search(r'(\d+[,.]?\d*)', ratings_text)
                    if ratings_val:
                        ratings_count = ratings_val.group(1).replace('.', '').replace(',', '')
                
                product_data = {
                    'nombre': title,
                    'estrellas': stars,
                    'calificaciones': ratings_count,
                    'precio': price,
                    'descuento': "Sin descuento",
                    'envio': "Estándar",
                    'url': product_url
                }
                
                products_list.append(product_data)
                
            except Exception as e:
                continue
        
        return products_list
    
    def extract_comments(self, product_url, max_comments=5):
        comments_data = []
        
        product_html = self.fetch_url(product_url)
        if not product_html:
            return comments_data
        
        time.sleep(random.uniform(1.0, 2.0))
        
        # Buscar bloques completos de comentarios
        comment_patterns = [
            r'<div[^>]*class="ui-review-capability-comments__comment[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>',
            r'<article[^>]*class="[^"]*ui-review-capability-reviews__review[^"]*"[^>]*>.*?</article>',
            r'<div[^>]*class="ui-review-capability__review[^"]*"[^>]*>.*?</div>\s*</div>'
        ]
        
        comment_blocks = []
        for pattern in comment_patterns:
            blocks = re.findall(pattern, product_html, re.DOTALL)
            if blocks:
                comment_blocks = blocks
                break
        
        # Procesar cada bloque de comentario
        for i, block in enumerate(comment_blocks[:max_comments]):
            try:
                # Extraer texto del comentario
                comment_text = ""
                text_patterns = [
                    r'<p[^>]*class="ui-review-capability-comments__comment__content[^"]*"[^>]*>(.*?)</p>',
                    r'<p[^>]*class="ui-review-capability__summary__plain_text__summary_container"[^>]*>(.*?)</p>'
                ]
                
                for pattern in text_patterns:
                    text_match = re.search(pattern, block, re.DOTALL)
                    if text_match:
                        comment_text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip()
                        comment_text = re.sub(r'\s+', ' ', comment_text).strip()
                        break
                
                # Extraer puntuación
                rating = "3"
                rating_match = re.search(r'<p class="andes-visually-hidden">Calificación (\d+) de 5</p>', block)
                
                if rating_match:
                    rating = rating_match.group(1)
                else:
                    # Intentar contar estrellas en el HTML
                    star_count = len(re.findall(r'<svg class="ui-review-capability-comments__comment__rating__star"', block))
                    if star_count > 0 and star_count <= 5:
                        rating = str(star_count)
                
                if comment_text:
                    comments_data.append({
                        'comentario': comment_text,
                        'puntuacion': rating
                    })
                
            except Exception as e:
                continue
        
        return comments_data
    
    def scrape_products(self, search_term, max_pages=1, get_comments=False, max_products_comments=10):
        all_products = []
        
        # Construir URL base
        if ' ' in search_term:
            formatted_search = search_term.replace(' ', '-')
            base_url = f"https://listado.mercadolibre.com.ar/{formatted_search}?sb=all_mercadolibre#D[A:{urllib.parse.quote(search_term)}]"
        else:
            base_url = f"https://listado.mercadolibre.com.ar/{search_term}#D[A:{search_term}]"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Scraping de páginas
        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}&page={page}"
            
            status_text.text(f"Extrayendo datos de la página {page}...")
            progress_bar.progress(page / max_pages * 0.7)
            
            page_html = self.fetch_url(page_url)
            if page_html:
                # Intentar extraer datos
                json_data = self.extract_json_data(page_html)
                page_products = []
                
                if json_data:
                    page_products = self.process_product_data(json_data)
                
                if not page_products:
                    page_products = self.extract_traditional_way(page_html)
                
                if page_products:
                    all_products.extend(page_products)
                    st.success(f"Se encontraron {len(page_products)} productos en la página {page}")
                else:
                    st.warning(f"No se pudieron extraer productos de la página {page}")
            
            if page < max_pages:
                time.sleep(random.uniform(2.0, 3.0))
        
        # Extraer comentarios si se solicita
        if get_comments and all_products:
            status_text.text("Extrayendo comentarios...")
            max_products_comments = min(max_products_comments, len(all_products))
            
            for count, product in enumerate(all_products[:max_products_comments]):
                if 'url' in product and product['url']:
                    progress = 0.7 + (count / max_products_comments) * 0.3
                    progress_bar.progress(progress)
                    status_text.text(f"Procesando comentarios {count+1}/{max_products_comments}: {product['nombre'][:30]}...")
                    
                    comments = self.extract_comments(product['url'], 5)
                    
                    # Agregar comentarios al producto
                    for i, comment in enumerate(comments):
                        product[f'comentario_{i+1}'] = comment['comentario']
                        product[f'puntuacion_comentario_{i+1}'] = comment['puntuacion']
                    
                    # Rellenar comentarios faltantes
                    for i in range(len(comments), 5):
                        product[f'comentario_{i+1}'] = ""
                        product[f'puntuacion_comentario_{i+1}'] = ""
                    
                    if count < max_products_comments - 1:
                        time.sleep(random.uniform(2.0, 3.0))
        
        progress_bar.progress(1.0)
        status_text.text("¡Scraping completado!")
        
        return all_products

class AnalizadorSentimiento:
    def __init__(self):
        self.palabras_positivas = [
            'excelente', 'bueno', 'buena', 'increíble', 'increible', 'delicioso', 'deliciosa',
            'suave', 'equilibrado', 'equilibrada', 'aromático', 'aromática', 'rico', 'rica',
            'agradable', 'elegante', 'intenso', 'intensa', 'fresco', 'fresca', 'fino', 'fina',
            'recomendable', 'espectacular', 'fantástico', 'fantástica', 'perfecto', 'perfecta',
            'sorprendente', 'impresionante', 'encantador', 'encantadora', 'satisfecho', 'satisfecha',
            'satisfactorio', 'satisfactoria', 'premium', 'calidad', 'maravilloso', 'maravillosa'
        ]
        
        self.palabras_negativas = [
            'malo', 'mala', 'horrible', 'terrible', 'desagradable', 'decepcionante',
            'áspero', 'aspero', 'ácido', 'acido', 'amargo', 'amarga', 'seco', 'seca',
            'flojo', 'floja', 'aguado', 'aguada', 'insípido', 'insipido', 'insipida',
            'insípida', 'ordinario', 'ordinaria', 'descompuesto', 'descompuesta',
            'vinagre', 'oxidado', 'oxidada', 'rancio', 'rancia'
        ]
        
        self.multiplicadores = [
            'muy', 'super', 'súper', 'tan', 'bastante', 'realmente',
            'extremadamente', 'verdaderamente', 'increíblemente', 'increiblemente',
            'totalmente', 'absolutamente', 'completamente', 'demasiado'
        ]
        
        self.negadores = [
            'no', 'nunca', 'jamás', 'jamas', 'ni', 'tampoco', 'apenas'
        ]
    
    def normalizar_texto(self, texto):
        if not isinstance(texto, str):
            return ""
        
        texto = texto.lower()
        
        # Eliminar acentos
        replacements = [
            ('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'),
            ('ü', 'u'), ('ñ', 'n')
        ]
        for orig, repl in replacements:
            texto = texto.replace(orig, repl)
        
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def calcular_sentimiento(self, comentario):
        if not comentario or not isinstance(comentario, str):
            return 3.0
        
        texto = self.normalizar_texto(comentario)
        palabras = texto.split()
        
        if not palabras:
            return 3.0
        
        puntuacion = 0
        contador_palabras_relevantes = 0
        
        i = 0
        while i < len(palabras):
            palabra = palabras[i]
            multiplicador = 1.0
            negacion = 1.0
            
            # Verificar multiplicadores y negadores
            j = max(0, i - 3)
            while j < i:
                if palabras[j] in self.multiplicadores:
                    multiplicador = 1.5
                if palabras[j] in self.negadores:
                    negacion = -1.0
                j += 1
            
            if palabra in self.palabras_positivas:
                puntuacion += 1.0 * multiplicador * negacion
                contador_palabras_relevantes += 1
            elif palabra in self.palabras_negativas:
                puntuacion -= 1.0 * multiplicador * negacion
                contador_palabras_relevantes += 1
            
            i += 1
        
        if contador_palabras_relevantes == 0:
            return 3.0
        
        promedio = puntuacion / contador_palabras_relevantes
        sentimiento = 3.0 + (promedio * 2.0)
        sentimiento = max(1.0, min(5.0, sentimiento))
        
        return sentimiento
    
    def analizar_productos(self, productos):
        resultados_productos = []
        
        for producto in productos:
            comentarios = []
            puntuaciones = []
            sentimientos = []
            
            # Extraer comentarios y puntuaciones del producto
            for i in range(1, 6):
                comentario_key = f'comentario_{i}'
                puntuacion_key = f'puntuacion_comentario_{i}'
                
                if comentario_key in producto and producto[comentario_key]:
                    comentario = producto[comentario_key]
                    comentarios.append(comentario)
                    
                    # Obtener puntuación original
                    try:
                        puntuacion = float(producto.get(puntuacion_key, 3.0))
                    except:
                        puntuacion = 3.0
                    puntuaciones.append(puntuacion)
                    
                    # Calcular sentimiento
                    sentimiento = self.calcular_sentimiento(comentario)
                    sentimientos.append(sentimiento)
            
            # Calcular promedios
            if sentimientos:
                sentimiento_promedio = statistics.mean(sentimientos)
                puntuacion_promedio = statistics.mean(puntuaciones)
            else:
                sentimiento_promedio = 3.0
                puntuacion_promedio = 3.0
            
            # Obtener precio
            try:
                precio = float(re.sub(r'[^\d.]', '', str(producto.get('precio', '0'))))
            except:
                precio = 0.0
            
            resultado = {
                'nombre_producto': producto.get('nombre', 'Sin nombre'),
                'sentimiento_promedio': round(sentimiento_promedio, 2),
                'calificacion_promedio': round(puntuacion_promedio, 2),
                'precio': precio,
                'estrellas': float(producto.get('estrellas', 0)),
                'num_comentarios': len(comentarios),
                'url': producto.get('url', '')
            }
            
            resultados_productos.append(resultado)
        
        return resultados_productos

def main():
    st.title("🛒 MercadoLibre Scraper & Análisis de Sentimientos")
    st.markdown("---")
    
    # Sidebar para configuración
    st.sidebar.header("⚙️ Configuración")
    
    # Parámetros de scraping
    search_term = st.sidebar.text_input("Término de búsqueda", value="vinos", help="Ejemplo: vinos, autos, cascos moto")
    max_pages = st.sidebar.slider("Número de páginas", 1, 5, 1)
    get_comments = st.sidebar.checkbox("Obtener comentarios", value=True)
    
    if get_comments:
        # Calcular el máximo teórico de productos según las páginas seleccionadas
        estimated_max_products = max_pages * 50  # Aproximadamente 50 productos por página
        
        # Mostrar información sobre productos estimados
        st.sidebar.info(f"📊 Productos estimados: ~{estimated_max_products} productos en {max_pages} página(s)")
        
        # Permitir seleccionar hasta el máximo estimado de productos
        max_products_comments = st.sidebar.slider(
            "Productos para comentarios", 
            1, 
            estimated_max_products, 
            min(50, estimated_max_products),  # Valor por defecto: mínimo entre 50 y el máximo estimado
            help=f"Puedes seleccionar hasta {estimated_max_products} productos para extraer comentarios"
        )
        
        # Mostrar tiempo estimado
        estimated_time_minutes = max_products_comments * 0.1  # Aproximadamente 6 segundos por producto
        st.sidebar.warning(f"⏱️ Tiempo estimado: ~{estimated_time_minutes:.1f} minutos")
    else:
        max_products_comments = 0
    
    # Botón de scraping
    if st.sidebar.button("🚀 Iniciar Scraping", type="primary"):
        if search_term:
            st.header(f"🔍 Resultados para: {search_term}")
            
            # Inicializar scraper
            scraper = MercadoLibreScraper()
            
            # Realizar scraping
            with st.spinner("Realizando scraping..."):
                productos = scraper.scrape_products(
                    search_term=search_term,
                    max_pages=max_pages,
                    get_comments=get_comments,
                    max_products_comments=max_products_comments
                )
            
            if productos:
                st.success(f"✅ Se encontraron {len(productos)} productos")
                
                # Convertir a DataFrame
                df_productos = pd.DataFrame(productos)
                
                # Tabs para mostrar resultados
                tab1, tab2, tab3 = st.tabs(["📊 Datos Extraídos", "🎯 Análisis de Sentimientos", "📥 Descargas"])
                
                with tab1:
                    st.subheader("Datos de Productos Extraídos")
                    
                    # Mostrar estadísticas básicas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Productos", len(productos))
                    with col2:
                        productos_con_precio = df_productos[df_productos['precio'].astype(str) != '0']
                        if not productos_con_precio.empty:
                            precio_promedio = pd.to_numeric(productos_con_precio['precio'], errors='coerce').mean()
                            st.metric("Precio Promedio", f"${precio_promedio:,.0f}" if not pd.isna(precio_promedio) else "N/A")
                        else:
                            st.metric("Precio Promedio", "N/A")
                    with col3:
                        productos_con_estrellas = df_productos[df_productos['estrellas'].astype(str) != '0']
                        if not productos_con_estrellas.empty:
                            estrellas_promedio = pd.to_numeric(productos_con_estrellas['estrellas'], errors='coerce').mean()
                            st.metric("Estrellas Promedio", f"{estrellas_promedio:.1f}" if not pd.isna(estrellas_promedio) else "N/A")
                        else:
                            st.metric("Estrellas Promedio", "N/A")
                    with col4:
                        productos_con_comentarios = sum(1 for p in productos if any(p.get(f'comentario_{i}', '') for i in range(1, 6)))
                        st.metric("Con Comentarios", productos_con_comentarios)
                    
                    # Mostrar tabla de productos
                    st.dataframe(df_productos, use_container_width=True)
                
                with tab2:
                    if get_comments:
                        st.subheader("🎯 Análisis de Sentimientos")
                        
                        # Realizar análisis de sentimientos
                        analizador = AnalizadorSentimiento()
                        
                        with st.spinner("Analizando sentimientos..."):
                            resultados_sentimiento = analizador.analizar_productos(productos)
                        
                        if resultados_sentimiento:
                            df_sentimientos = pd.DataFrame(resultados_sentimiento)
                            
                            # Métricas de sentimiento
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                sent_promedio = df_sentimientos['sentimiento_promedio'].mean()
                                st.metric("Sentimiento Promedio", f"{sent_promedio:.2f} ⭐")
                            with col2:
                                mejor_producto = df_sentimientos.loc[df_sentimientos['sentimiento_promedio'].idxmax()]
                                st.metric("Mejor Valorado", f"{mejor_producto['sentimiento_promedio']:.2f} ⭐")
                            with col3:
                                total_con_comentarios = len(df_sentimientos[df_sentimientos['num_comentarios'] > 0])
                                st.metric("Productos Analizados", total_con_comentarios)
                            
                            # Top 10 productos por sentimiento
                            st.subheader("🏆 Top 10 Productos por Sentimiento")
                            top_productos = df_sentimientos.nlargest(10, 'sentimiento_promedio')
                            
                            for idx, producto in top_productos.iterrows():
                                with st.expander(f"#{idx+1} {producto['nombre_producto'][:60]}... - {producto['sentimiento_promedio']} ⭐"):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**Sentimiento:** {producto['sentimiento_promedio']} ⭐")
                                        st.write(f"**Calificación Original:** {producto['calificacion_promedio']}")
                                        st.write(f"**Precio:** ${producto['precio']:,.0f}")
                                    with col2:
                                        st.write(f"**Estrellas ML:** {producto['estrellas']}")
                                        st.write(f"**Comentarios:** {producto['num_comentarios']}")
                                        if producto['url']:
                                            st.link_button("Ver en MercadoLibre", producto['url'])
                            
                            # Tabla completa de resultados de sentimiento
                            st.subheader("📊 Resultados Completos")
                            st.dataframe(df_sentimientos.sort_values('sentimiento_promedio', ascending=False), use_container_width=True)
                            
                            # Guardar resultados en session state para descarga
                            st.session_state['df_sentimientos'] = df_sentimientos
                    else:
                        st.info("Para realizar análisis de sentimientos, activa la opción 'Obtener comentarios' en la configuración.")
                
                with tab3:
                    st.subheader("📥 Descargar Resultados")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Datos de Productos**")
                        
                        # Crear CSV de productos
                        csv_productos = df_productos.to_csv(index=False, encoding='utf-8')
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename_productos = f"{search_term.replace(' ', '_')}_productos_{timestamp}.csv"
                        
                        st.download_button(
                            label="⬇️ Descargar CSV Productos",
                            data=csv_productos,
                            file_name=filename_productos,
                            mime='text/csv'
                        )
                    
                    with col2:
                        if 'df_sentimientos' in st.session_state:
                            st.write("**Análisis de Sentimientos**")
                            
                            # Crear CSV de sentimientos
                            csv_sentimientos = st.session_state['df_sentimientos'].to_csv(index=False, encoding='utf-8')
                            filename_sentimientos = f"{search_term.replace(' ', '_')}_sentimientos_{timestamp}.csv"
                            
                            st.download_button(
                                label="⬇️ Descargar CSV Sentimientos",
                                data=csv_sentimientos,
                                file_name=filename_sentimientos,
                                mime='text/csv'
                            )
                        else:
                            st.info("No hay datos de sentimientos para descargar.")
                
                # Guardar productos en session state
                st.session_state['productos'] = productos
                st.session_state['df_productos'] = df_productos
                
            else:
                st.error("❌ No se pudieron encontrar productos. Intenta con otro término de búsqueda.")
        else:
            st.warning("⚠️ Por favor, ingresa un término de búsqueda.")
    
    # Sección de información
    st.markdown("---")
    
    # Mostrar resultados previos si existen
    if 'productos' in st.session_state and st.session_state['productos']:
        st.header("📋 Sesión Actual")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"Productos cargados: {len(st.session_state['productos'])}")
        with col2:
            if st.button("🗑️ Limpiar Datos"):
                for key in ['productos', 'df_productos', 'df_sentimientos']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    # Sección de ayuda e información
    with st.expander("ℹ️ Información y Ayuda"):
        st.markdown("""
        ### 🎯 ¿Qué hace esta aplicación?
        
        Esta herramienta permite:
        - **Extraer productos** de MercadoLibre mediante web scraping
        - **Obtener comentarios** y calificaciones de productos
        - **Analizar sentimientos** de los comentarios usando procesamiento de lenguaje natural
        - **Descargar resultados** en formato CSV
        
        ### 🚀 Cómo usar:
        
        1. **Configura la búsqueda** en el panel lateral:
           - Ingresa el término de búsqueda (ej: "vinos", "notebooks", "celulares")
           - Selecciona el número de páginas a analizar (1-5 páginas)
           - Activa la extracción de comentarios si deseas análisis de sentimiento
           - **NUEVO:** Ahora puedes extraer comentarios de hasta 250 productos (5 páginas × 50 productos)
        
        2. **Inicia el scraping** haciendo clic en "Iniciar Scraping"
        
        3. **Revisa los resultados** en las pestañas:
           - **Datos Extraídos**: Información básica de productos
           - **Análisis de Sentimientos**: Valoración automática de comentarios
           - **Descargas**: Descarga los resultados en CSV
        
        ### 📊 Análisis de Sentimientos:
        
        El sistema analiza automáticamente los comentarios y asigna una puntuación de 1 a 5 estrellas basada en:
        - **Palabras positivas**: excelente, bueno, recomendable, etc.
        - **Palabras negativas**: malo, terrible, decepcionante, etc.
        - **Modificadores**: muy, super, bastante (intensifican el sentimiento)
        - **Negaciones**: no, nunca, jamás (invierten el sentimiento)
        
        ### ⚠️ Consideraciones:
        
        - El scraping puede tomar varios minutos dependiendo del número de páginas y productos
        - Cada producto con comentarios toma aproximadamente 6 segundos en procesarse
        - **Tiempo estimado para 250 productos: ~25 minutos**
        - Algunos productos pueden no tener comentarios disponibles
        - Los resultados dependen de la estructura actual de MercadoLibre
        - Se incluyen pausas entre solicitudes para evitar bloqueos
        
        ### 🔧 Parámetros Recomendados:
        
        - **Para pruebas rápidas**: 1 página, 10-20 productos con comentarios (~2-3 minutos)
        - **Para análisis medio**: 2-3 páginas, 50-100 productos con comentarios (~8-15 minutos)
        - **Para análisis completo**: 4-5 páginas, 150-250 productos con comentarios (~20-25 minutos)
        
        ### 📁 Archivos de Salida:
        
        - **Productos CSV**: Contiene toda la información extraída de productos
        - **Sentimientos CSV**: Contiene el análisis de sentimientos resumido por producto
        
        ### 🆕 Mejoras en esta versión:
        
        - **Límite dinámico**: El número máximo de productos para comentarios se ajusta automáticamente según las páginas seleccionadas
        - **Mejor estimación de tiempo**: Muestra el tiempo estimado antes de iniciar el proceso
        - **Información más clara**: Indica cuántos productos se pueden procesar según las páginas seleccionadas
        """)
    
    # Footer con información adicional
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 20px;'>
            <p>🛒 <strong>MercadoLibre Scraper & Análisis</strong> - Versión Mejorada</p>
            <p>Herramienta para extracción y análisis de productos de MercadoLibre</p>
            <p><em>Desarrollado con Streamlit y Python - Ahora con soporte para hasta 250 productos</em></p>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()