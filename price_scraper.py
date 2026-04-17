import asyncio
import threading
import time
import os
import random  
import undetected_chromedriver as uc
import shutil  
import re 
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class PriceScraperService:
    def __init__(self):
        self.inside_email = os.getenv("INSIDE_EMAIL")
        self.inside_password = os.getenv("INSIDE_PASSWORD")
        self.forma_login = os.getenv("FORMA_LOGIN")
        self.forma_password = os.getenv("FORMA_PASSWORD")
        self.fourcars_login = os.getenv("FOURCARS_LOGIN")
        self.fourcars_password = os.getenv("FOURCARS_PASSWORD")
        self.autonova_login = os.getenv("AUTONOVAD_LOGIN")
        self.autonova_password = os.getenv("AUTONOVAD_PASSWORD")

        self.preferred_brands = ["POLCAR", "VAG", "VW", "SIGNEDA", "DPA", "FPS"]

        self.lock = threading.RLock() 
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        self._init_browser()
        print("✅ Всі 4 сайти з цінами готові до бою!")

    def _init_browser(self):
        print("🚀 Налаштовую Chrome для PriceBot...")
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-networking")
        
        bot_profile_path = os.path.join(os.getcwd(), "bot_profile")
        self.driver = uc.Chrome(user_data_dir=bot_profile_path, options=options, version_main=146)
        
        self.driver.maximize_window()
        self.main_window = self.driver.current_window_handle
        
        self.driver.execute_script("window.open('https://inside-auto.com/', '_blank');")
        self.inside_tab = self.driver.window_handles[-1]
        time.sleep(0.5)
        
        self.driver.execute_script("window.open('https://b2b.forma-parts.ua/', '_blank');")
        self.forma_tab = self.driver.window_handles[-1]
        time.sleep(0.5)
        
        self.driver.execute_script("window.open('https://4cars.com.ua/?action=user_login', '_blank');")
        self.fourcars_tab = self.driver.window_handles[-1]
        time.sleep(0.5)

        self.driver.execute_script("window.open('https://autonovad.ua/', '_blank');")
        self.autonova_tab = self.driver.window_handles[-1]
        time.sleep(0.5)
        
        if self.inside_email: self._auto_login_inside()
        if self.forma_login: self._auto_login_forma()
        if self.fourcars_login: self._auto_login_fourcars()
        if self.autonova_login: self._auto_login_autonova()

        self.driver.switch_to.window(self.main_window)
        self._warmup_browser()

    def _human_delay(self, min_s=0.2, max_s=0.5):
        time.sleep(random.uniform(min_s, max_s))

    def _shorten_days(self, text):
        return re.sub(r'днів|дні|день', 'дн.', text, flags=re.IGNORECASE)

    def _warmup_browser(self):
        print("🔥 Починаю 'прогрів' браузера...")
        warmup_articles = ["FP 1237 391", "FP 6415 228", "95x2025"]
        dummy_article = random.choice(warmup_articles)
        try:
            self._parse_inside_auto_sync(dummy_article)
            self._parse_forma_sync(dummy_article)
            self._parse_fourcars_sync(dummy_article)
            self._parse_autonova_sync(dummy_article)
            print("✅ Прогрів успішно завершено!")
        except Exception as e: print(f"⚠️ Помилка прогріву: {e}")

    def restart_browser(self):
        with self.lock: 
            print("♻️ Перезапуск Chrome...")
            try: self.driver.quit()
            except: pass
            time.sleep(3)
            bot_profile_path = os.path.join(os.getcwd(), "bot_profile")
            try: shutil.rmtree(bot_profile_path, ignore_errors=True)
            except: pass
            self._init_browser()

    def _is_forma_logged_in(self): return len(self.driver.find_elements(By.XPATH, "//input[@name='Login']")) == 0
    def _is_fourcars_logged_in(self): return len(self.driver.find_elements(By.NAME, "login")) == 0
    def _is_inside_logged_in(self): return len(self.driver.find_elements(By.XPATH, "//a[@href='/customer']")) > 0
    def _is_autonova_logged_in(self):
        btns = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Увійти')]")
        return len([btn for btn in btns if btn.is_displayed()]) == 0

    def _perfect_clear_input(self, element):
        try:
            self.driver.execute_script("window.focus();")
            element.click()
            self._human_delay(0.05, 0.1)
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.BACKSPACE)
            self._human_delay(0.05, 0.1)
            element.send_keys(Keys.END)
            element.send_keys(Keys.BACKSPACE * 30)
            self._human_delay(0.1, 0.2)
        except: pass

    # --- ЛОГІНИ ---
    def _auto_login_autonova(self):
        try:
            self.driver.switch_to.window(self.autonova_tab)
            self.driver.execute_script("window.focus();")
            self.driver.get("https://autonovad.ua/")
            time.sleep(4) 
            if self._is_autonova_logged_in(): return
            wait = WebDriverWait(self.driver, 10)
            login_modal_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Увійти')]")))
            self.driver.execute_script("arguments[0].click();", login_modal_btn)
            modal = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-dialog")))
            time.sleep(1) 
            login_input = modal.find_element(By.CSS_SELECTOR, "input[type='text'].form-control")
            pass_input = modal.find_element(By.CSS_SELECTOR, "input[type='password'].form-control")
            submit_btn = modal.find_element(By.XPATH, ".//button[contains(text(), 'Увійти')]")
            self._perfect_clear_input(login_input)
            login_input.send_keys(self.autonova_login)
            time.sleep(0.5)
            self._perfect_clear_input(pass_input)
            pass_input.send_keys(self.autonova_password)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(5)
        except Exception as e: print(f"❌ Помилка логіну Autonova-D: {e}")

    def _auto_login_fourcars(self):
        try:
            self.driver.switch_to.window(self.fourcars_tab)
            self.driver.execute_script("window.focus();")
            if "/?action=user_login" not in self.driver.current_url:
                self.driver.get("https://4cars.com.ua/?action=user_login")
                time.sleep(3)
            if self._is_fourcars_logged_in(): return
            wait = WebDriverWait(self.driver, 10)
            login_input = wait.until(EC.presence_of_element_located((By.NAME, "login")))
            pass_input = self.driver.find_element(By.NAME, "password")
            submit_btn = self.driver.find_element(By.NAME, "auth")
            login_input.click(); time.sleep(0.2)
            self._perfect_clear_input(login_input)
            login_input.send_keys(self.fourcars_login)
            pass_input.click(); time.sleep(0.2)
            self._perfect_clear_input(pass_input)
            pass_input.send_keys(self.fourcars_password)
            submit_btn.click()
            time.sleep(5)
        except Exception as e: print(f"❌ Помилка логіну 4cars: {e}")

    def _auto_login_inside(self):
        try:
            self.driver.switch_to.window(self.inside_tab)
            self.driver.execute_script("window.focus();")
            self.driver.get("https://inside-auto.com/")
            time.sleep(4) 
            if self._is_inside_logged_in(): return
            login_btn = self.driver.find_element(By.XPATH, "//a[@data-target='#login']")
            self.driver.execute_script("arguments[0].click();", login_btn)
            time.sleep(2) 
            email_tab = self.driver.find_element(By.XPATH, "//span[@data-type='email']")
            self.driver.execute_script("arguments[0].click();", email_tab)
            time.sleep(2) 
            all_emails = self.driver.find_elements(By.XPATH, "//input[@name='email']")
            all_passwords = self.driver.find_elements(By.XPATH, "//input[@name='password']")
            visible_email = next((el for el in all_emails if el.is_displayed()), None)
            visible_pass = next((el for el in all_passwords if el.is_displayed()), None)
            if visible_email and visible_pass:
                self.driver.execute_script("arguments[0].value = arguments[1];", visible_email, self.inside_email)
                self.driver.execute_script("arguments[0].value = arguments[1];", visible_pass, self.inside_password)
                time.sleep(1)
                submit_btn = self.driver.find_element(By.XPATH, "//input[@type='submit' and @value='Вхід']")
                self.driver.execute_script("arguments[0].click();", submit_btn)
                time.sleep(6)
        except Exception as e: print(f"❌ Помилка логіну Inside-Auto: {e}")

    def _auto_login_forma(self):
        try:
            self.driver.switch_to.window(self.forma_tab)
            self.driver.execute_script("window.focus();")
            self.driver.get("https://b2b.forma-parts.ua/")
            time.sleep(4)
            if self._is_forma_logged_in(): return
            wait = WebDriverWait(self.driver, 10)
            login_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='Login']")))
            pass_input = self.driver.find_element(By.XPATH, "//input[@name='Password']")
            login_input.click(); time.sleep(0.2)
            self._perfect_clear_input(login_input)
            login_input.send_keys(self.forma_login)
            pass_input.click(); time.sleep(0.2)
            self._perfect_clear_input(pass_input)
            pass_input.send_keys(self.forma_password)
            time.sleep(1)
            pass_input.send_keys(Keys.RETURN)
            time.sleep(6)
        except Exception as e: print(f"❌ Помилка логіну Forma Parts: {e}")

    # --- ПАРСИНГ ---
    def _parse_autonova_sync(self, article):
        with self.lock:
            result_dict = {"exact": {}, "analogs": {}}
            try:
                self.driver.switch_to.window(self.autonova_tab)
                self.driver.execute_script("window.focus();")
                self.driver.get("https://autonovad.ua/")
                self._human_delay(1.0, 1.3)
                
                if not self._is_autonova_logged_in():
                    self._auto_login_autonova()
                    if not self._is_autonova_logged_in(): return result_dict

                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[name='search']")
                search_input = next((el for el in inputs if el.is_displayed()), None)
                if not search_input: return result_dict
                
                self._perfect_clear_input(search_input)
                search_input.send_keys(article)
                
                btns = self.driver.find_elements(By.CSS_SELECTOR, "button.header__to-search")
                search_btn = next((btn for btn in btns if btn.is_displayed()), None)
                if search_btn: self.driver.execute_script("arguments[0].click();", search_btn)
                else: search_input.send_keys(Keys.RETURN)
                
                def wait_condition(d):
                    offers = d.find_elements(By.CSS_SELECTOR, "div.offer")
                    if any(o.is_displayed() for o in offers): return True
                    
                    empty = d.find_elements(By.CSS_SELECTOR, "div.search-result__empty, div.not-found")
                    if any(e.is_displayed() for e in empty): return True
                    
                    clarify = d.find_elements(By.XPATH, "//a[contains(translate(text(), 'УТОЧНИТИ ЦІНИ', 'уточнити ціни'), 'уточнити ціни')]")
                    if any(c.is_displayed() for c in clarify): return True
                    
                    return False

                try:
                    WebDriverWait(self.driver, 20).until(wait_condition)
                    time.sleep(5.0) 
                except Exception as e:
                    logger.warning(f"Таймаут очікування даних Autonova для {article}")

                # Блок уточнення ціни
                try:
                    clarify_links = [el for el in self.driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'УТОЧНИТИ ЦІНИ', 'уточнити ціни'), 'уточнити ціни')]") if el.is_displayed()]
                    if clarify_links:
                        clicked = False
                        for target_brand in self.preferred_brands:
                            for link in clarify_links:
                                try:
                                    parent_text = link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'product-card')]").get_attribute("textContent").upper()
                                    if target_brand in parent_text:
                                        self.driver.execute_script("arguments[0].click();", link)
                                        clicked = True; break
                                except:
                                    try:
                                        parent_text = link.find_element(By.XPATH, "./../../..").get_attribute("textContent").upper()
                                        if target_brand in parent_text:
                                            self.driver.execute_script("arguments[0].click();", link)
                                            clicked = True; break
                                    except: pass
                            if clicked: break
                        
                        if not clicked:
                            self.driver.execute_script("arguments[0].click();", clarify_links[0])
                            
                        WebDriverWait(self.driver, 15).until(
                            lambda d: any(o.is_displayed() for o in d.find_elements(By.CSS_SELECTOR, "div.offer")) or 
                                      any(e.is_displayed() for e in d.find_elements(By.CSS_SELECTOR, "div.search-result__empty"))
                        )
                        time.sleep(5.0)
                except: pass 

                search_art_clean = re.sub(r'[^A-Z0-9]', '', article.upper())
                panels = self.driver.find_elements(By.CSS_SELECTOR, "div.panel")

                # Тимчасовий словник з новою логікою: Склад -> Деталь -> [Ціни]
                grouped_data = {"exact": {}, "analogs": {}}

                for panel in panels:
                    try:
                        try:
                            cat_name = panel.find_element(By.CSS_SELECTOR, "div.panel_title").get_attribute("textContent").strip().split('\n')[0]
                        except:
                            try:
                                cat_name = panel.find_element(By.CSS_SELECTOR, "div.panel__title").get_attribute("textContent").strip().split('\n')[0]
                            except:
                                cat_name = "Залишки"
                    except:
                        cat_name = "Залишки"

                    offers = panel.find_elements(By.CSS_SELECTOR, "div.offer")

                    for offer in offers:
                        try:
                            try:
                                brand_col = offer.find_element(By.CSS_SELECTOR, "div.offer__brand div.col__value")
                                try:
                                    art_elem = brand_col.find_element(By.CSS_SELECTOR, ".offer__product-code, a")
                                    art_text = art_elem.get_attribute("textContent").strip()
                                    full_text = brand_col.get_attribute("textContent").strip()
                                    brand_text = full_text.replace(art_text, "").strip()
                                    brand_art_full = f"{brand_text} {art_text}".strip()
                                except:
                                    brand_art_full = " ".join(brand_col.get_attribute("textContent").split())
                            except:
                                brand_art_full = "Деталь"
                                
                            parsed_art_clean = re.sub(r'[^A-Z0-9]', '', brand_art_full.upper())
                            is_exact = bool(search_art_clean and search_art_clean in parsed_art_clean)
                            
                            try:
                                qty_col = offer.find_element(By.CSS_SELECTOR, "div.offer__quantity div.col__value")
                                qty = qty_col.get_attribute("textContent").replace("шт.", "").replace("шт", "").strip()
                            except: qty = "Н/Д"
                                
                            try:
                                term_col = offer.find_element(By.CSS_SELECTOR, "div.offer__delivery-times div.col__value")
                                term_raw = term_col.get_attribute("textContent").strip().replace('\n', ' ')
                                term = re.split(r'\(|при', term_raw)[0].strip()
                            except: 
                                term = "Н/Д"
                                term_raw = ""
                                
                            try:
                                price_val = offer.find_element(By.CSS_SELECTOR, "span.price__value")
                                price = price_val.get_attribute("textContent").strip()
                            except: price = "Н/Д"
                            
                            term = self._shorten_days(term)
                            icon = "⏱" if "0" in term or "сьогодні" in term_raw.lower() else "⏳"
                            
                            res_line = f"{icon} {term} | 📦 {qty} | 💰 {price} грн."
                            
                            brand_art_key = f"🔹 *{brand_art_full}*"
                            target_type = "exact" if is_exact else "analogs"
                            
                            # ГРУПУВАННЯ: Спочатку Склад, потім Деталь
                            if cat_name not in grouped_data[target_type]:
                                grouped_data[target_type][cat_name] = {}
                                
                            if brand_art_key not in grouped_data[target_type][cat_name]:
                                grouped_data[target_type][cat_name][brand_art_key] = []
                            
                            if len(grouped_data[target_type][cat_name][brand_art_key]) < 8:
                                grouped_data[target_type][cat_name][brand_art_key].append(res_line)
                                
                        except Exception as e: continue 

                # ФОРМАТУВАННЯ: Перетворюємо ієрархію для main.py
                for target_type in ["exact", "analogs"]:
                    for cat_name, items_in_cat in grouped_data[target_type].items():
                        formatted_cat_name = f"📂 *{cat_name}*"
                        result_dict[target_type][formatted_cat_name] = []
                        
                        for brand_art, offers_list in items_in_cat.items():
                            result_dict[target_type][formatted_cat_name].append(brand_art)
                            result_dict[target_type][formatted_cat_name].extend(offers_list)
                            result_dict[target_type][formatted_cat_name].append("") # Порожній рядок-відступ між різними деталями в одному складі
                            
                        # Прибираємо останній порожній рядок, щоб не було дір перед наступним складом
                        if result_dict[target_type][formatted_cat_name] and result_dict[target_type][formatted_cat_name][-1] == "":
                            result_dict[target_type][formatted_cat_name].pop()
                            
                return result_dict
                
            except Exception as e: 
                logger.error(f"❌ Помилка парсингу Autonova-D: {e}")
                return result_dict
            finally: self.driver.switch_to.window(self.main_window)

    def _parse_inside_auto_sync(self, article):
        with self.lock:
            result_dict = {"exact": {}, "analogs": {}}
            try:
                self.driver.switch_to.window(self.inside_tab)
                self.driver.execute_script("window.focus();")
                self.driver.get("https://inside-auto.com/")
                self._human_delay(0.8, 1.1)
                
                if not self._is_inside_logged_in(): self._auto_login_inside()
                
                wait = WebDriverWait(self.driver, 10)
                search_input = wait.until(EC.presence_of_element_located((By.ID, "search_input")))
                search_input.click()
                self._human_delay(0.1, 0.2)
                self._perfect_clear_input(search_input)
                search_input.send_keys(article)
                self._human_delay(0.2, 0.4) 
                
                try:
                    search_btn = self.driver.find_element(By.ID, "button_search")
                    self.driver.execute_script("arguments[0].click();", search_btn)
                except: search_input.send_keys(Keys.RETURN)
                
                self._human_delay(0.8, 1.1)
                
                try:
                    clarify_links = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-group li.list-group-item a")
                    if clarify_links:
                        clicked = False
                        for target_brand in self.preferred_brands:
                            for link in clarify_links:
                                if target_brand in link.text.upper():
                                    self.driver.execute_script("arguments[0].click();", link)
                                    clicked = True; break
                            if clicked: break
                        if not clicked: self.driver.execute_script("arguments[0].click();", clarify_links[0])
                        self._human_delay(0.8, 1.2)
                except: pass

                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, "div.row.item.brand") or 
                                  "нічого" in d.page_source.lower() or "не знай" in d.page_source.lower()
                    )
                    time.sleep(1)
                except: pass
                
                try:
                    show_more_btns = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-link') and contains(@id, 'show-buttom')]")
                    for btn in show_more_btns: self.driver.execute_script("arguments[0].click();", btn)
                    if show_more_btns: self._human_delay(0.3, 0.5)
                except: pass
                
                items = self.driver.find_elements(By.CSS_SELECTOR, "div.row.item.brand")
                if not items: return result_dict
                
                for item in items:
                    try:
                        label = item.find_element(By.CSS_SELECTOR, "div.label_info_detail").text.strip().lower()
                        is_exact = "точне" in label
                    except: is_exact = False 
                    
                    try: title = item.find_element(By.CSS_SELECTOR, "div.col-md-3 a").text.strip().replace("\n", " ")
                    except: continue 
                    
                    brand_art_key = f"🔹 *{title}*"
                    target_dict = result_dict["exact"] if is_exact else result_dict["analogs"]
                    
                    if brand_art_key not in target_dict:
                        target_dict[brand_art_key] = []
                    
                    rows = item.find_elements(By.CSS_SELECTOR, "table tr")
                    for row in rows:
                        try:
                            term = row.find_element(By.CLASS_NAME, "search-product-term").get_attribute("textContent").strip()
                            qty = row.find_element(By.CLASS_NAME, "search-product-quantity").get_attribute("textContent").strip()
                            price = row.find_element(By.CLASS_NAME, "search-product-price").get_attribute("textContent").strip()
                            
                            term = " ".join(term.split())
                            qty = " ".join(qty.split())
                            price = " ".join(price.split())

                            if not term and not price: continue
                            
                            term = self._shorten_days(term)
                            term = re.sub(r'(\d+)([a-zA-Zа-яА-ЯіІїЇєЄґҐ]+)', r'\1 \2', term)
                            qty_clean = qty.replace("шт.", "").replace("шт", "").strip()
                            
                            icon = "⏱" if any(x in term.lower() for x in ["ч", "год", "сегод"]) else "⏳"
                            res_line = f"{icon} {term} | 📦 {qty_clean} | 💰 {price}"
                            
                            if len(target_dict[brand_art_key]) < 8:
                                target_dict[brand_art_key].append(res_line)
                        except: continue
                        
                return result_dict
            except Exception as e: return result_dict
            finally: self.driver.switch_to.window(self.main_window)

    def _parse_forma_sync(self, article):
        with self.lock:
            result_dict = {"exact": {}, "analogs": {}}
            try:
                self.driver.switch_to.window(self.forma_tab)
                self.driver.execute_script("window.focus();")
                self.driver.get("https://b2b.forma-parts.ua/")
                self._human_delay(0.8, 1.2)
                
                if not self._is_forma_logged_in():
                    self._auto_login_forma()
                    if not self._is_forma_logged_in(): return result_dict

                wait = WebDriverWait(self.driver, 10)
                search_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Пошук']")))
                
                try:
                    clear_btn = self.driver.find_element(By.CSS_SELECTOR, "i.mdi-close")
                    if clear_btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", clear_btn)
                        self._human_delay(0.2, 0.4) 
                except: pass 
                
                search_input.click()
                self._human_delay(0.1, 0.2)
                self._perfect_clear_input(search_input)
                search_input.send_keys(article)
                self._human_delay(0.8, 1.1)
                search_input.send_keys(Keys.RETURN)
                self._human_delay(1.2, 1.5)
                
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.XPATH, "//div[contains(@class, 'item-line')]") or 
                                  "не знайдений" in d.page_source or "не знайдено" in d.page_source
                    )
                    time.sleep(1)
                except: pass
                
                items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'item-line')]")
                if not items: return result_dict 
                
                for item in items[:4]:
                    try:
                        try: brand = item.find_element(By.CSS_SELECTOR, "div.line-title dd").text.strip()
                        except:
                            try: brand = item.find_element(By.CSS_SELECTOR, "div.line-title div.flex.grow > div").text.strip().split('\n')[0]
                            except: brand = "Н/Д"
                            
                        try: art = item.find_element(By.CSS_SELECTOR, "div.line-title input").get_attribute("value").strip()
                        except: art = "Н/Д"
                            
                        search_art_clean = re.sub(r'[^A-Z0-9]', '', article.upper())
                        parsed_art_clean = re.sub(r'[^A-Z0-9]', '', art.upper())
                        is_exact = search_art_clean and parsed_art_clean != "НД" and (search_art_clean in parsed_art_clean or parsed_art_clean in search_art_clean)

                        price = "Немає ціни"
                        try:
                            price_elem = item.find_element(By.XPATH, ".//span[contains(@class, 'price')]")
                            actions = ActionChains(self.driver)
                            actions.move_to_element(price_elem).perform()
                            self._human_delay(0.2, 0.3) 
                            
                            wait_for_tooltip = WebDriverWait(self.driver, 3)
                            tooltip_price = wait_for_tooltip.until(lambda d: d.find_element(By.XPATH, "//div[contains(@class, 'v-tooltip__content') and contains(@class, 'menuable__content__active')]"))
                            wait_for_tooltip.until(lambda d: "Закупівля" in tooltip_price.text)
                            
                            raw_price_text = tooltip_price.text.strip()
                            if "Закупівля:" in raw_price_text:
                                for line in raw_price_text.split('\n'):
                                    if "Закупівля:" in line:
                                        val = line.split("Закупівля:")[1].strip()
                                        price = f"{val.replace(' ', '')} грн."
                                        break
                        except:
                            try:
                                price_elem = item.find_element(By.XPATH, ".//span[contains(@class, 'price')]")
                                full_text = price_elem.text.replace(' ', '').replace('\n', '')
                                price = f"{full_text} грн. (Продаж)"
                            except: pass
                            
                        availability = "Невідомо"
                        try:
                            cube_block = item.find_element(By.XPATH, ".//span[contains(@class, 'cube-block')]")
                            actions = ActionChains(self.driver)
                            actions.move_to_element(cube_block).perform()
                            self._human_delay(0.2, 0.3) 
                            tooltip = self.driver.find_element(By.XPATH, "//div[contains(@class, 'v-tooltip__content') and contains(@class, 'menuable__content__active')]")
                            raw_avail = tooltip.text.strip()
                            if raw_avail: 
                                qty_clean = raw_avail.replace("шт.", "").replace("шт", "").strip()
                                availability = qty_clean.replace("\n", " | 📦 ")
                        except: availability = "Не вдалося перевірити"

                        if art == "Н/Д" and brand == "Н/Д": continue

                        res_line = f"📦 {availability} | 💰 {price}"
                        brand_art_key = f"🔹 *{brand} {art}*"
                        target_dict = result_dict["exact"] if is_exact else result_dict["analogs"]

                        if brand_art_key not in target_dict:
                            target_dict[brand_art_key] = []
                        
                        if len(target_dict[brand_art_key]) < 5:
                            target_dict[brand_art_key].append(res_line)

                    except: continue
                return result_dict
            except Exception as e: return result_dict
            finally: self.driver.switch_to.window(self.main_window)

    def _parse_fourcars_sync(self, article):
        with self.lock:
            result_dict = {"exact": {}, "analogs": {}}
            try:
                self.driver.switch_to.window(self.fourcars_tab)
                self.driver.execute_script("window.focus();")
                self.driver.get("https://4cars.com.ua/")
                self._human_delay(0.8, 1.1)
                
                if not self._is_fourcars_logged_in():
                    self._auto_login_fourcars()
                    if not self._is_fourcars_logged_in(): return result_dict
                
                wait = WebDriverWait(self.driver, 10)
                try: search_input = wait.until(EC.presence_of_element_located((By.NAME, "code")))
                except: return result_dict
                
                search_input.click()
                self._human_delay(0.1, 0.2)
                self._perfect_clear_input(search_input)
                
                search_input.send_keys(article)
                search_input.send_keys(Keys.RETURN)
                
                self._human_delay(1.0, 1.4)
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, "table.datatable tbody tr") or
                                  "ничего не найдено" in d.page_source
                    )
                    time.sleep(1)
                except: pass
                
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table.datatable tbody tr")
                if not rows or "ничего не найдено" in rows[0].text: return result_dict 
                
                parsing_analogs = False

                for row in rows:
                    try:
                        try:
                            separator_text = row.find_element(By.TAG_NAME, "b").text.strip().lower()
                            if "замены для запрошенного кода" in separator_text:
                                parsing_analogs = True 
                                continue 
                        except: pass 

                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 5: continue
                        
                        col0_text = cols[0].text.strip().split('\n')
                        if len(col0_text) >= 3:
                            brand = col0_text[0].strip()
                            art = col0_text[1].strip()
                        else:
                            brand = "Деталь"
                            art = ""
                            
                        availability = cols[2].text.strip()
                        term = cols[3].text.strip()
                        
                        term = self._shorten_days(term)
                        term_str = f"{term} дн." if term.isdigit() else term
                        
                        try: price = row.find_element(By.CLASS_NAME, "table_price").text.strip()
                        except: price = cols[5].text.strip()
                            
                        icon = "⏳" if term.isdigit() and int(term) > 0 else "⏱"
                        qty_clean = availability.replace("шт.", "").replace("шт", "").strip()
                        
                        res_line = f"{icon} {term_str} | 📦 {qty_clean} | 💰 {price}"
                        brand_art_key = f"🔹 *{brand} {art}*"
                        target_dict = result_dict["analogs"] if parsing_analogs else result_dict["exact"]
                        
                        if brand_art_key not in target_dict:
                            target_dict[brand_art_key] = []
                            
                        if len(target_dict[brand_art_key]) < 8:
                            target_dict[brand_art_key].append(res_line)
                            
                    except: continue
                return result_dict
            except Exception as e: return result_dict
            finally: self.driver.switch_to.window(self.main_window)

    async def search_inside(self, article):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._parse_inside_auto_sync, article)

    async def search_fps(self, article):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._parse_forma_sync, article)

    async def search_fourcars(self, article):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._parse_fourcars_sync, article)

    async def search_autonova(self, article):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._parse_autonova_sync, article)