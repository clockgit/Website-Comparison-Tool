import os
import re
import time
import requests
import click
import string
from selenium.webdriver.common.by import By
import re
from bs4 import BeautifulSoup
from difflib import HtmlDiff
from urllib.parse import urljoin
from selenium import webdriver
from PIL import Image, ImageChops
from inspect import getmembers, isfunction
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class WebsiteComparer:
    def __init__(self):
        self.ff_options = webdriver.FirefoxOptions()
        self.ff_options.add_argument("--headless")
        self.c_options = webdriver.ChromeOptions()
        self.c_options.add_argument("--headless")
        self.mode = 0o755
        self.baseDir = './report/'
        self.checked_urls = {}
        self.debug = False

    def get_page_urls(self, url):
        response = requests.get(url)

        if response.status_code != 200:
            print("Error: Website could not be accessed.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a")

        page_urls = []
        for link in links:
            href = link.get("href")
            if href and not href.startswith("#")and not href.startswith("javascript"):
                page_url = urljoin(url, href)
                if page_url not in page_urls:
                    page_urls.append(page_url)
        return page_urls

    def check_links(self, page_urls):
        broken_links = []
        for url in page_urls:
            response = requests.head(url)
            if response.status_code not in [200, 301, 302, 403]:
                broken_links.append(f"({response.status_code}) {url}")
                self.log(f"Broken link for {url}: {response.status_code}: {url}")
        return broken_links

    def analyze_page_load_times(self, driver, url, dir, site, path):
        navigation_start = driver.execute_script("return window.performance.timing.navigationStart")
        load_event_end = driver.execute_script("return window.performance.timing.loadEventEnd")
        page_load_time = (load_event_end - navigation_start) / 1000
        self.checked_urls[path][site]['load_time'] = page_load_time
        self.log(f"{url} Page load: {page_load_time:.2f} seconds", dir)

    def diff(self, param):
        diff = HtmlDiff()
        website1_html = param["driver1"].page_source
        website2_html = param["driver2"].page_source
        content_diff = diff.make_file(website1_html.splitlines(), website2_html.splitlines())
        with open(f"{param['dir']}/html_diff.html", "w", encoding="utf-8") as file:
            file.write(content_diff)
        file.close()
        self.log(f"Created: {param['dir']}/content_diff.html", param['dir'])

    def compare_page(self, url1, url2, browser, debug = False):
        self.debug = debug
        if browser == "f":
            driver1 = webdriver.Firefox(options=self.ff_options)
            driver2 = webdriver.Firefox(options=self.ff_options)
        elif browser == "c":
            driver1 = webdriver.Chrome(options=self.c_options)
            driver2 = webdriver.Chrome(options=self.c_options)
        else:
            print("Please select browser with c or f.")
            quit()

        s1 = self.check_url(url1)
        s2 = self.check_url(url2, s1)

        param = {
            "1st": s1,
            "2nd": s2,
            "base_dir": self.baseDir,
            "driver1": driver1,
            "driver2": driver2,
        }

        if(param['1st']['exist']):
            self.log(f"Skipping: {url1}", self.baseDir)
        else:
            # Create dir structure.
            param['dir'] = os.path.join(self.baseDir, param['1st']['path'] )
            os.makedirs(param['dir'], mode = self.mode, exist_ok = True)

            self.log(f"Starting param:\r\n{param}", self.baseDir)

            # Ensure the main-content element loaded
            try:
                driver1.get(url1)
                driver2.get(url2)
                main_1 = WebDriverWait(driver1, 5).until(
                    EC.presence_of_element_located((By.ID, "main-content"))
                )
                main_2 = WebDriverWait(driver2, 5).until(
                    EC.presence_of_element_located((By.ID, "main-content"))
                )
                # Analyze page load times.
                self.analyze_page_load_times(driver1, url1, param['dir'], 's1', param['1st']['path'])
                self.analyze_page_load_times(driver2, url2, param['dir'], 's2', param['1st']['path'])
                # Check for differences in page content
#                 self.diff(param)
                # Check for visual differences using screenshots
                self.image_diff(param)
                # Compare page URLs
#                 site1_page_urls = self.get_page_urls(url1)
#                 site2_page_urls = self.get_page_urls(url2)
#                 self.save_page_urls(url1, site1_page_urls, f"{param['dir']}/site1_page_links.txt")
#                 self.save_page_urls(url2, site2_page_urls, f"{param['dir']}/site2_page_links.txt")
#                 site1_broken_links = self.check_links(site1_page_urls)
#                 site2_broken_links = self.check_links(site2_page_urls)
#                 self.save_page_urls(url1, site1_broken_links, f"{param['dir']}/site1_broken_links.txt")
#                 self.save_page_urls(url2, site2_broken_links, f"{param['dir']}/site2_broken_links.txt")
                create_reports(self, param['1st']['path'])

            except Exception as e:
                print(f'Exception: {e}')
            finally:
                driver1.quit()
                driver2.quit()

    def check_url(self, url, s1 = False):
        r = {"exist": True, "url": url}
        pattern_page = "^(?:https?://)(?:www.)?[^/]+.[a-z]{3,5}.+/([^?#/]+)"
        pattern_site = "^(?:https?://)(?:www.)?([^/]+.[a-z]{3,5})"
        pattern_path = "^(?:https?://)(?:www.)?([a-z]+.gov/[^?#=]+)"
        if match := re.search(pattern_site, url, re.IGNORECASE):
            r["site"] = match.group(1)
        else:
            return r
        if match := re.search(pattern_path, url, re.IGNORECASE):
            r["path"] = match.group(1)
        else:
            r["path"] = f"{r['site']}/"
        if match := re.search(pattern_page, url, re.IGNORECASE):
            r["page"] = match.group(1)
        else:
            r["page"] = 'home'
        if r["path"] in self.checked_urls.keys():
          r["exist"] = True
        else:
          r["exist"] = False
          if s1 == False:
            self.checked_urls[r["path"]] = {'s1': {'site': r["site"], 'page': r["page"], 'path': r["path"], 'url': url}}
          else:
            self.checked_urls[s1['path']]['s2'] = {'site': r["site"], 'page': r["page"], 'path': r["path"], 'url': url}
        return r

    def take_screenshot(self, driver, path, name):
        self.log(f"take_screenshot(self, {driver}, {path}, {name})")
        #driver.set_window_size(1700, 900)
        driver.set_window_size(1700, 900)
        driver.execute_script('window.scrollTo(0, 0);')
#         driver.execute_script('let h = document.getElementsByTagName("header");for (let i = 0; i < h.length; i++) {h[i].style.display = "none";}')
#         driver.execute_script('let f = document.getElementsByTagName("footer");for (let i = 0; i < f.length; i++) {f[i].style.display = "none";}')
        img_url = f"{path}/{name}"
        driver.get_screenshot_as_file(img_url)
        return Image.open(img_url).convert('RGB')

    def image_diff(self, param):
        self.log(f"image_diff(self, {param})", self.baseDir)
        image1 = self.take_screenshot(param['driver1'], param['dir'], 'site_1.png')
        image2 = self.take_screenshot(param['driver2'], param['dir'], 'site_2.png')
        diff_image = ImageChops.difference(image1, image2)
        visual_diff = f"{param['dir']}/diff.png"
        diff_image.save(visual_diff)
        msg = 'yes'
        if diff_image.getbbox():
            msg = 'no'
            print(f"Visual differences saved to {visual_diff}")
        else:
            print("No visual differences.")
        self.checked_urls[param['1st']['path']]['diff'] = {'match': msg, 'image': visual_diff}
        self.checked_urls[param['1st']['path']]['s1']['image'] = f"{param['dir']}/site_1.png"
        self.checked_urls[param['1st']['path']]['s2']['image'] = f"{param['dir']}/site_2.png"


    def log(self, msg, dir = './report/'):
        if self.debug:
            print(f"Debug:\r\n{msg}\r\n")
        if(dir != self.baseDir):
            f = open(dir + '/page.log', 'a')
            f.write(f"{msg}\r\n")
            f.close()
        f = open('report/main.log', 'a')
        f.write(f"{msg}\r\n")
        f.close()

    def save_page_urls(self, url, page_urls, filename):
        with open(filename, "w") as file:
            file.write(f"Page URLs for {url}:\n")
            for page_url in page_urls:
                file.write(page_url + "\n")
        self.log(f"URLs saved to {filename}.")
    def create_report_start(self, d1, d2):
        with open('./report/report.html', "w") as file:
                file.write("<head><style>td{padding:5px;} img{width: 100%; height: auto;} .image{width:170px;} .even{background-color: #CCC;}</style>\r\n")
                file.write("<body>\r\n")
                file.write(f'<a href="images.html">image</a>\r\n')
                file.write(f"<h1>{d1}<br/>{d2}</h1>\r\n")
                file.write('<table>\r\n')
                file.write("<tr>\r\n")
                #file.write("<th>Site1</th>")
                file.write("<th>page</th>")
                file.write("<th>path</th>")
                file.write(f'<th class="image">{d1}</th>')
                #file.write("<th>Site2</th>")
                #file.write("<th>page</th>")
                #file.write("<th>path</th>")
                file.write(f'<th class="image">{d2}</th>')
                file.write("<th>Match</th>")
                file.write('<th class="image">Diff</th>\r\n')
                file.write('<th>Load Time</th>')
                file.write("</tr>\r\n")
        with open('./report/images.html', "w") as file:
                file.write("<head><style>.space{padding:5px 0;} .path{width:4vw;} table{width:100%} td{padding:10px;} .site{width:25%} .dif{width:75%;} img{width: 100%; height: auto;} .even{background-color: #fcc;} .odd{background-color: #cfc;}</style>\r\n")
                file.write("<body>\r\n")
                file.write(f'<a href="report.html">main report</a>\r\n')
                file.write(f"<h1>{d1}<br/>{d2}</h1>\r\n")
                file.write('<table>\r\n')
                file.write("<tr>\r\n")
                file.write('<th class="site">Site</th>')
                file.write('<th class="diff">Diff</th>\r\n')
                file.write("</tr>\r\n")
    def create_report_end(self):
        with open('./report/report.html', "w") as file:
            file.write("</table>\r\n")
            file.write("</body>\r\n")
        with open('./report/images.html', "w") as file:
            file.write("</table>\r\n")
            file.write("</body>\r\n")
    def create_reports(self, data):
        with open('./report/report.html', "w") as file:
            file.write(f'<tr class="{c}">\r\n')
            #file.write(f"<td>{data['s1']['site']}</td>")
            file.write(f"<td>{data['s1']['page']}</td>")
            file.write(f"<td>{data['s1']['path']}</td>")
            img = data['s1']['image'].replace("./report/", "").replace("//", "/")
            file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')

            #file.write(f"<td>{data['s2']['site']}</td>")
            #file.write(f"<td>{data['s2']['page']}</td>")
            #file.write(f"<td>{data['s2']['path']}</td>")
            img = data['s2']['image'].replace("./report/", "").replace("//", "/")
            file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')

            file.write(f"<td>{data['diff']['match']}</td>")
            img = data["diff"]["image"].replace("./report/", "").replace("//", "/")
            file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')
            file.write(f'<td>{data['s1']['load_time']} / {data['s2']['load_time']}</td>\r\n')
            file.write("</tr>\r\n")

        with open('./report/images.html', "w") as file:
            img1 = data['s1']['image'].replace("./report/", "").replace("//", "/")
            img2 = data['s2']['image'].replace("./report/", "").replace("//", "/")
            diff = data["diff"]["image"].replace("./report/", "").replace("//", "/")
            file.write(f'<tr class="{c}">\r\n')
            file.write('<td class="site">')
            file.write('<h2 class="space">')
            file.write(f'{data['s1']['page']}')
            file.write('</h2>')
            file.write('<div class="space">')
            file.write(f'<a title="{data['s1']['url']}" href="{data['s1']['url']}" target="_blank">S1</a><br />')
            file.write(f'Load: {data['s1']['load_time']}<br />')
            file.write(f'<a href="{img1}" target="_blank"><img src="{img1}"></a>')
            file.write('</div>')

            file.write('<div class="space">')
            file.write(f'<a title="{data['s2']['url']}" href="{data['s2']['url']}" target="_blank">S2</a><br />')
            file.write(f'Load: {data['s2']['load_time']}<br />')
            file.write(f'<a href="{img2}" target="_blank"><img src="{img2}"></a>')
            file.write('</div>')

            file.write('</td>')

            file.write(f'<td class="diff"><a href="{diff}" target="_blank"><img src="{diff}" width="33vw"></a></td>\r\n')
            file.write("</tr>\r\n")


if __name__ == "__main__":
    comparer = WebsiteComparer()
    browser = click.prompt("(c)hrome or (f)ireFox", default="f")
    d1 = click.prompt("Enter the first domain:", default="https://www.gsa.gov")
    d2 = click.prompt("Enter the second domain:", default="https://gsa-test-d10.gsa-ecas.cloud")

    comparer.create_report_start(d1, d2)

    with open('paths.txt') as f:
        count = len(f.readlines())
        x = 0
    with open('paths.txt') as f:
        for line in f:
            x = x+1
            p1 = f"{d1}{line}".replace("\n", "").replace("\r", "")
            p2 = f"{d2}{line}".replace("\n", "").replace("\r", "")
            print(f"Comparing ({x} of {count}):\n    {p1}\n    {p2}")
            comparer.compare_page(
                f"{p1}",
                f"{p2}",
                browser
            )

    comparer.create_report_end(d1, d2)