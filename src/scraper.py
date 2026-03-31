import requests
from bs4 import BeautifulSoup
import datetime
import io
from pypdf import PdfReader
from concurrent.futures import ThreadPoolExecutor, as_completed

class RegulationScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.sources = [
            {"name": "Resmi Gazete", "url": "https://www.resmigazete.gov.tr/", "type": "resmigazete"},
            {"name": "KVKK", "url": "https://www.kvkk.gov.tr/Icerik/Duyurular", "type": "kvkk"},
            {"name": "MEB", "url": "https://mevzuat.meb.gov.tr/", "type": "meb"},
            {"name": "GİB", "url": "https://www.gib.gov.tr/mevzuat", "type": "gib"},
            {"name": "BDDK", "url": "https://www.bddk.org.tr/Mevzuat", "type": "bddk"},
            {"name": "SPK", "url": "https://spk.gov.tr/duyurular", "type": "spk"},
            {"name": "EPDK", "url": "https://www.epdk.gov.tr/Detay/Icerik/3-0-0/mevzuat", "type": "epdk"},
            {"name": "Competition Authority", "url": "https://www.rekabet.gov.tr/tr/Mevzuat", "type": "rekabet"},
            {"name": "BTK", "url": "https://www.btk.gov.tr/mevzuat", "type": "btk"}
        ]

    def _extract_pdf_content(self, pdf_url):
        try:
            response = requests.get(pdf_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            with io.BytesIO(response.content) as f:
                reader = PdfReader(f)
                text = "".join(page.extract_text() + "\n" for page in reader.pages[:10])
                return text.strip()
        except Exception as e:
            return f"PDF reading error: {str(e)}"

    def _fetch_single_page(self, url, source_config, keyword=None, target_date=None):
        regs = []
        source_type = source_config["type"]
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200: return regs
            
            soup = BeautifulSoup(response.content, 'html.parser')
            target_area = soup.find("div", {"id": "content"}) if source_type == "kvkk" else soup
            links = (target_area or soup).find_all("a")
            
            for link in links:
                text = link.text.strip()
                href = link.get('href')
                if not text or not href: continue
                
                text_lower = text.lower()
                
                if source_type == "resmigazete":
                    if keyword and keyword.lower() not in text_lower: continue
                elif source_type == "kvkk":
                    if len(text) < 10: continue
                    if keyword and keyword.lower() not in text_lower: continue
                elif source_type == "meb":
                    valid = any(x in text_lower for x in ["yönetmelik", "yönerge", "genelge"])
                    if not valid and not keyword: continue
                    if keyword and keyword.lower() not in text_lower: continue
                elif source_type == "gib":
                    valid = any(x in text_lower for x in ["kanun", "tebliğ", "sirküler", "yönetmelik"])
                    if not valid and not keyword: continue
                    if keyword and keyword.lower() not in text_lower: continue
                else: 
                    valid = any(term in text_lower for term in ["yönetmelik", "tebliğ", "kurul kararı", "duyuru", "mevzuat", "genelge", "kanun"])
                    if not valid and not keyword: continue
                    if keyword and keyword.lower() not in text_lower: continue

                domain = '/'.join(source_config["url"].split('/')[:3])
                full_url = href if href.startswith("http") else f"{domain}/{href.lstrip('/')}"
                
                content = self._extract_pdf_content(full_url) if full_url.lower().endswith(".pdf") else f"For details: {full_url}"
                
                regs.append({
                    "title": text.replace("––", "").strip(),
                    "date": target_date if target_date else datetime.date.today().isoformat(),
                    "content": content,
                    "source": source_config["name"],
                    "link": full_url
                })
        except: pass
        return regs

    def unified_run(self, keyword=None, days=1):
        all_results = []
        tasks = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            for source in self.sources:
                if source["type"] == "resmigazete":
                    today = datetime.date.today()
                    for i in range(days):
                        t_date = today - datetime.timedelta(days=i)
                        url = f"https://www.resmigazete.gov.tr/fihrist?tarih={t_date.strftime('%Y-%m-%d')}"
                        tasks.append(executor.submit(self._fetch_single_page, url, source, keyword, t_date.isoformat()))
                
                elif source["type"] == "kvkk":
                    current_year = datetime.date.today().year
                    num_years = max(1, (days // 365) + 1)
                    for year in range(current_year, current_year - num_years, -1):
                        url = f"https://www.kvkk.gov.tr/Icerik/{year}/Duyurular"
                        tasks.append(executor.submit(self._fetch_single_page, url, source, keyword))
                
                else:
                    tasks.append(executor.submit(self._fetch_single_page, source["url"], source, keyword))

            for future in as_completed(tasks):
                all_results.extend(future.result())
        
        return all_results
