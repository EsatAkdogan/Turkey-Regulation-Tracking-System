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
                text = ""
                for page in reader.pages[:10]:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            return f"PDF reading error: {str(e)}"

    def fetch_regulations(self):
        all_regulations = []

        tasks = [
            (self._scrape_resmi_gazete, ()),
            (self._scrape_kvkk, ()),
            (self._scrape_meb, ()),
            (self._scrape_gib, ()),
            (self._scrape_generic_gov, ("BDDK", "https://www.bddk.org.tr/Mevzuat")),
            (self._scrape_generic_gov, ("SPK", "https://spk.gov.tr/duyurular")),
            (self._scrape_generic_gov, ("EPDK", "https://www.epdk.gov.tr/Detay/Icerik/3-0-0/mevzuat")),
            (self._scrape_generic_gov, ("Competition Authority", "https://www.rekabet.gov.tr/tr/Mevzuat")),
            (self._scrape_generic_gov, ("BTK", "https://www.btk.gov.tr/mevzuat"))
        ]
        
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_source = {executor.submit(func, *args): func.__name__ for func, args in tasks}
            for future in as_completed(future_to_source):
                try:
                    all_regulations.extend(future.result())
                except Exception:
                    pass
                    
        return all_regulations
    
    def search_online(self, keyword, days=30):
        tasks = [
            (self._deep_scrape_resmi_gazete, {"days": days, "keyword": keyword}),
            (self._scrape_kvkk, {"keyword": keyword, "days": days}),
            (self._scrape_meb, {"keyword": keyword}),
            (self._scrape_gib, {"keyword": keyword})
        ]
        
        for source in ["BDDK", "SPK", "EPDK", "Competition Authority", "BTK"]:
            url = next(s["url"] for s in self.sources if s["name"] == source)
            tasks.append((self._scrape_generic_gov, {"source_name": source, "url": url, "keyword": keyword}))
            
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_source = {executor.submit(func, **kwargs): func.__name__ for func, kwargs in tasks}
            for future in as_completed(future_to_source):
                try:
                    results = future.result()
                    if results:
                        yield results
                except Exception:
                    pass

    def _deep_scrape_resmi_gazete(self, days=7, keyword=None):
        regulations = []
        base_url = "https://www.resmigazete.gov.tr/"
        today = datetime.date.today()
        
        def fetch_date(i):
            target_date = today - datetime.timedelta(days=i)
            date_str = target_date.strftime("%Y%m%d")
            year = target_date.strftime("%Y")
            month = target_date.strftime("%m")
            archive_url = f"https://www.resmigazete.gov.tr/eskiler/{year}/{month}/{date_str}.htm"
            
            if i == 0:
                archive_url = base_url
            
            day_regs = []
            try:
                response = requests.get(archive_url, headers=self.headers, timeout=5)
                if response.status_code != 200:
                    return day_regs
                
                soup = BeautifulSoup(response.content, 'html.parser')
                all_links = soup.find_all("a")
                
                for link in all_links:
                    text = link.text.strip()
                    href = link.get('href')
                    if not text or not href:
                        continue
                    if keyword and keyword.lower() not in text.lower():
                        continue
                    
                    full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    content = f"For details: {full_url}"
                    if full_url.lower().endswith(".pdf"):
                        content = self._extract_pdf_content(full_url)
                    
                    
                    text = text.replace("––", "").strip()
                    
                    day_regs.append({
                        "title": text,
                        "date": target_date.isoformat(),
                        "content": content,
                        "source": "Resmi Gazete",
                        "link": full_url
                    })
            except Exception:
                pass
            return day_regs

       
        max_workers = 10 if days > 10 else days
        if max_workers < 1: max_workers = 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_day = {executor.submit(fetch_date, i): i for i in range(days)}
            for future in as_completed(future_to_day):
                regulations.extend(future.result())
                
        return regulations

    def _scrape_resmi_gazete(self):
        return self._deep_scrape_resmi_gazete(days=1)

    def _scrape_kvkk(self, keyword=None, days=365):
        regulations = []
        base_url = "https://www.kvkk.gov.tr"
        
        #Years to scrape
        current_year = datetime.date.today().year
        num_years = max(1, (days // 365) + 1)
        target_urls = [f"https://www.kvkk.gov.tr/Icerik/{year}/Duyurular" for year in range(current_year, current_year - num_years, -1)]
        
        for target_url in target_urls:
            try:
                response = requests.get(target_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    content_div = soup.find("div", {"id": "content"}) or soup.body
                    if content_div:
                        links = content_div.find_all("a")
                        for link in links:
                            text = link.text.strip()
                            href = link.get('href')
                            if not text or len(text) < 10 or not href:
                                continue
                            if keyword and keyword.lower() not in text.lower():
                                continue
                            full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                            
                            content = f"For details: {full_url}"
                            if full_url.lower().endswith(".pdf"):
                                content = self._extract_pdf_content(full_url)
                                
                            regulations.append({
                                "title": text,
                                "date": datetime.date.today().isoformat(),
                                "content": content,
                                "source": "KVKK",
                                "link": full_url
                            })
                    break 
            except Exception:
                continue
        return regulations

    def _scrape_meb(self, keyword=None):
        regulations = []
        base_url = "https://mevzuat.meb.gov.tr"
        try:
            response = requests.get(base_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all("a")
                for link in links:
                    text = link.text.strip()
                    href = link.get('href')
                    if not text or len(text) < 10 or not href:
                        continue
                    if "yönetmelik" not in text.lower() and "yönerge" not in text.lower() and "genelge" not in text.lower():
                        if not keyword: continue
                    if keyword and keyword.lower() not in text.lower():
                        continue
                    full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    content = f"For details: {full_url}"
                    if full_url.lower().endswith(".pdf"):
                        content = self._extract_pdf_content(full_url)
                        
                    regulations.append({
                        "title": text,
                        "date": datetime.date.today().isoformat(), 
                        "content": content,
                        "source": "MEB",
                        "link": full_url
                    })
        except Exception:
            pass
        return regulations

    def _scrape_gib(self, keyword=None):
        regulations = []
        base_url = "https://www.gib.gov.tr"
        target_url = "https://www.gib.gov.tr/mevzuat"
        try:
            response = requests.get(target_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all("a")
                for link in links:
                    text = link.text.strip()
                    href = link.get('href')
                    if not text or len(text) < 10 or not href:
                        continue
                    valid_terms = ["kanun", "tebliğ", "sirküler", "yönetmelik"]
                    if not any(term in text.lower() for term in valid_terms):
                        if not keyword: continue
                    if keyword and keyword.lower() not in text.lower():
                        continue
                    full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    content = f"For details: {full_url}"
                    if full_url.lower().endswith(".pdf"):
                        content = self._extract_pdf_content(full_url)
                        
                    regulations.append({
                        "title": text,
                        "date": datetime.date.today().isoformat(), 
                        "content": content,
                        "source": "GİB",
                        "link": full_url
                    })
        except Exception:
            pass
        return regulations

    def _scrape_generic_gov(self, source_name, url, keyword=None):
        regulations = []
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all("a")
                seen_links = set()
                
                for link in links:
                    text = link.text.strip()
                    href = link.get('href')
                    
                    if not text or len(text) < 10 or not href:
                        continue
                    
                    if href in seen_links:
                        continue
                    seen_links.add(href)

                    
                    valid_terms = ["yönetmelik", "tebliğ", "kurul kararı", "duyuru", "mevzuat", "genelge", "kanun"]
                    if not any(term in text.lower() for term in valid_terms):
                        if not keyword: continue
                    
                    if keyword and keyword.lower() not in text.lower():
                        continue

                    full_url = href if href.startswith("http") else f"{'/'.join(url.split('/')[:3])}/{href.lstrip('/')}"
                    
                    content = f"For details: {full_url}"
                    if full_url.lower().endswith(".pdf"):
                        content = self._extract_pdf_content(full_url)
                    
                    regulations.append({
                        "title": text,
                        "date": datetime.date.today().isoformat(),
                        "content": content,
                        "source": source_name,
                        "link": full_url
                    })
        except Exception:
            pass
        return regulations

