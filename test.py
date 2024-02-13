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
        self.ff_options.add_argument("--width=2560")
        self.ff_options.add_argument("--height=1440")
        self.c_options = webdriver.ChromeOptions()
        self.c_options.add_argument("--headless")
        self.c_options.add_argument("--window-size=2560,1440")
        self.mode = 0o755
        self.baseDir = './report/'
        self.checked_urls = {}
        self.debug = False
        self.tags = {
            'header': "//header[@role='banner']",
            'footer': "//footer[@role='contentinfo']",
            'main': "//main[@id='main-content']",
        }
        self.by = By.XPATH

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
        return broken_links

    def analyze_page_load_times(self, driver, url, dir, site, path):
        navigation_start = driver.execute_script("return window.performance.timing.navigationStart")
        load_event_end = driver.execute_script("return window.performance.timing.loadEventEnd")
        page_load_time = (load_event_end - navigation_start) / 1000
        self.checked_urls[path][site]['load_time'] = page_load_time

    def diff(self, param):
        diff = HtmlDiff()
        website1_html = param["driver1"].page_source
        website2_html = param["driver2"].page_source
        content_diff = diff.make_file(website1_html.splitlines(), website2_html.splitlines())
        with open(f"{param['dir']}/html_diff.html", "w", encoding="utf-8") as file:
            file.write(content_diff)
        file.close()

    def setup(self, folder = './report/', browser = 'c', debug = False):
        self.debug = debug
        self.baseDir = folder
        if browser == "f":
            self.driver1 = webdriver.Firefox(options=self.ff_options)
            self.driver2 = webdriver.Firefox(options=self.ff_options)
        elif browser == "c":
            self.driver1 = webdriver.Chrome(options=self.c_options)
            self.driver2 = webdriver.Chrome(options=self.c_options)
        else:
            print("Please select browser with c or f.")
            quit()

    def shutdown(self):
        self.driver1.quit()
        self.driver2.quit()

    def compare_page(self, url1, url2):
        s1 = self.check_url(url1)
        s2 = self.check_url(url2, s1)

        param = {
            "1st": s1,
            "2nd": s2,
            "base_dir": self.baseDir,
            "driver1": self.driver1,
            "driver2": self.driver2,
        }

        if(s1['exist']):
            print('Duplicate path detected, skipping!')
        else:
            # Create dir structure.
            param['dir'] = os.path.join(self.baseDir, param['1st']['path'] )
            os.makedirs(param['dir'], mode = self.mode, exist_ok = True)

            # Ensure the main-content element loaded
            try:
                self.driver1.get(url1)
                self.driver2.get(url2)
                WebDriverWait(self.driver1, 10).until(
                    EC.all_of(
                        EC.presence_of_element_located((By.ID, "main-content")),
                        EC.presence_of_element_located((By.ID, "ZN_0d171YnFuvpJle6")),
                    )
                )
                WebDriverWait(self.driver2, 10).until(
                    EC.all_of(
                        EC.presence_of_element_located((By.ID, "main-content")),
                        EC.presence_of_element_located((By.ID, "ZN_0d171YnFuvpJle6")),
                    )
                )
                #WebDriverWait(self.driver1, 5).until(
                #    EC.presence_of_element_located((By.ID, "main-content"))
                #)
                #WebDriverWait(self.driver2, 5).until(
                #    EC.presence_of_element_located((By.ID, "main-content"))
                #)
                # Analyze page load times.
                self.analyze_page_load_times(self.driver1, url1, param['dir'], 's1', param['1st']['path'])
                self.analyze_page_load_times(self.driver2, url2, param['dir'], 's2', param['1st']['path'])
                # Check for differences in page content
                #self.diff(param)
                # Check for visual differences using screenshots
                self.image_diff(param, 'header')
                self.image_diff(param, 'main')
                self.image_diff(param, 'footer')
                # Compare page URLs
                #site1_page_urls = self.get_page_urls(url1)
                #site2_page_urls = self.get_page_urls(url2)
                #self.save_page_urls(url1, site1_page_urls, f"{param['dir']}/site1_page_links.txt")
                #self.save_page_urls(url2, site2_page_urls, f"{param['dir']}/site2_page_links.txt")
                #site1_broken_links = self.check_links(site1_page_urls)
                #site2_broken_links = self.check_links(site2_page_urls)
                #self.save_page_urls(url1, site1_broken_links, f"{param['dir']}/site1_broken_links.txt")
                #self.save_page_urls(url2, site2_broken_links, f"{param['dir']}/site2_broken_links.txt")
                self.create_reports(self.checked_urls[param['1st']['path']])

            except Exception as e:
                if hasattr(e, 'message'):
                    print(e)
                    print(e.message)
                else:
                    print(e)
            #finally:
                #print(f'checked {url1} {url2}')

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
            self.checked_urls[r["path"]] = {'s1': {'site': r["site"], 'page': r["page"], 'path': r["path"], 'url': url, 'image':{}}, 's2':{}, 'diff':{}}
        else:
            self.checked_urls[s1['path']]['s2'] = {'site': r["site"], 'page': r["page"], 'path': r["path"], 'url': url, 'image':{}, 'diff':{}}
        return r

    def take_screenshot(self, driver, path, name, tag = 'main'):
        img_url = f"{path}/{name}"
        ######
        #original_size = driver.get_window_size()
        #required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
        #required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        #driver.set_window_size(required_width, required_height)
        #driver.execute_script('window.scrollTo(0, 0);')
        el = driver.find_element(self.by, self.tags[tag])
        el.screenshot(img_url)  # avoids scrollbar
        #driver.set_window_size(original_size['width'], original_size['height'])
        ######
        #driver.set_window_size(1700, 900)
        #driver.get_screenshot_as_file(img_url)
        return Image.open(img_url).convert('RGB')

    def image_diff(self, param, tag='main'):
        #time.sleep(5)
        image1 = self.take_screenshot(param['driver1'], param['dir'], tag + '_site_1.png', tag)
        image2 = self.take_screenshot(param['driver2'], param['dir'], tag + '_site_2.png', tag)
        diff_image = ImageChops.difference(image1, image2)
        visual_diff = f"{param['dir']}/{tag}_diff.png"
        diff_image.save(visual_diff)
        msg = 'yes'
        if diff_image.getbbox():
            msg = 'no'
            #print(f"Visual differences saved to {visual_diff}")
        #else:
            #print("No visual differences.")

        self.checked_urls[param['1st']['path']]['diff'][tag] = {'match': msg, 'image': visual_diff}
        self.checked_urls[param['1st']['path']]['s1']['image'][tag] = f"{param['dir']}/{tag}_site_1.png"
        self.checked_urls[param['1st']['path']]['s2']['image'][tag] = f"{param['dir']}/{tag}_site_2.png"


    def save_page_urls(self, url, page_urls, filename):
        with open(filename, "w") as file:
            file.write(f"Page URLs for {url}:\n")
            for page_url in page_urls:
                file.write(page_url + "\n")
    def create_report_start(self, d1, d2):
        start = "<head><style>.space{padding:5px 0;} .path{width:4vw;} table{width:100%} td{padding:10px;} .site{width:25%} .dif{width:75%;} img{width: 100%; height: auto;} tr:nth-child(2n+2) {background-color: #FCC;} tr:nth-child(2n+3) {background-color: #CFC;}</style>\r\n<body>\r\n<h1>" + f'd1: {d1}<br/>d2: {d2}' + "</h1>\r\n<table>\r\n"
        with open(f'{self.baseDir}report.html', "w") as file:
                for tag in self.tags:
                    file.write(f'<a class="space" href="{tag}.html">{tag}</a>\r\n')
                file.write(start)

                file.write("<tr>\r\n")
                #file.write("<th>Site1</th>")
                file.write("<th>page</th>")
                file.write("<th>path</th>")
                file.write('<th>Load Time</th>')
                for tag in self.tags:
                    file.write(f'<th class="image">d1 {tag}</th>')
                    file.write(f'<th class="image">d2 {tag}</th>')
                    file.write(f'<th class="image">Diff {tag}</th>\r\n')
                file.write("</tr>\r\n")
        for tag in self.tags:
            with open(f'{self.baseDir}{tag}.html', "w") as file:
                    file.write(f'<a href="report.html">main report</a>\r\n')
                    file.write(f'<h1>{tag}</h1>')
                    file.write(start)

                    file.write("<tr>\r\n")
                    file.write('<th class="site">Site</th>')
                    file.write('<th class="diff">Diff</th>\r\n')
                    file.write("</tr>\r\n")
    def create_report_end(self):
        end = "</table>\r\n</body>\r\n"
        with open(f'{self.baseDir}report.html', "a") as file:
            file.write(end)
        for tag in self.tags:
            with open(f'{self.baseDir}{tag}.html', "a") as file:
                file.write(end)

    def create_reports(self, data):
        with open(f'{self.baseDir}report.html', "a") as file:
            file.write(f'<tr>\r\n')
            #file.write(f"<td>{data['s1']['site']}</td>")
            file.write(f"<td>{data['s1']['page']}</td>")
            file.write(f"<td>{data['s1']['path']}</td>")
            file.write(f"<td>{data['s1']['load_time']} / {data['s2']['load_time']}</td>\r\n")

            for tag in self.tags:
                img = data['s1']['image'][tag].replace(self.baseDir, "").replace("//", "/")
                file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')
                img = data['s2']['image'][tag].replace(self.baseDir, "").replace("//", "/")
                file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')

                if data["diff"][tag]['match'] == 'no':
                    img = data["diff"][tag]['image'].replace(self.baseDir, "").replace("//", "/")
                    file.write(f'<td><a href="{img}" target="_blank"><img src="{img}"></a></td>\r\n')
                else:
                    file.write(f'<td>Match</td>\r\n')

            file.write("</tr>\r\n")

        for tag in self.tags:
            with open(f'{self.baseDir}{tag}.html', "a") as file:
                file.write(f'<tr>\r\n')
                file.write('<td class="site">')
                file.write('<h2 class="space">')
                file.write(f"{data['s1']['page']}")
                file.write('</h2>')
                file.write('<div class="space">')
                file.write(f"<a title=\"{data['s1']['url']}\" href=\"{data['s1']['url']}\" target=\"_blank\">S1</a><br />")
                file.write(f"Load: {data['s1']['load_time']}<br />")
                file.write(f'Page section: {tag}')
                img1 = data['s1']['image'][tag].replace(self.baseDir, "").replace("//", "/")
                file.write(f'<a href="{img1}" target="_blank"><img src="{img1}"></a>')
                file.write('</div>')

                file.write('<div class="space">')
                file.write(f"<a title=\"{data['s2']['url']}\" href=\"{data['s2']['url']}\" target=\"_blank\">S2</a><br />")
                file.write(f"Load: {data['s2']['load_time']}<br />")
                img2 = data['s2']['image'][tag].replace(self.baseDir, "").replace("//", "/")
                file.write(f'<a href="{img2}" target="_blank"><img src="{img2}"></a>')
                file.write('</div>')

                file.write('</td>')
                file.write(f'<td class="diff">')
                if data["diff"][tag]['match'] == 'no':
                    diff = data["diff"][tag]["image"].replace(self.baseDir, "").replace("//", "/")
                    file.write(f'<a href="{diff}" target="_blank"><img src="{diff}" width="33vw"></a>')
                else:
                    file.write('Pixel perfect match!')
                file.write("</td>\r\n</tr>\r\n")


if __name__ == "__main__":
    comparer = WebsiteComparer()
    browser = click.prompt("(c)hrome or (f)ireFox", default="f")
    d1 = click.prompt("Enter the first domain:", default="https://www.gsa.gov")
    #d2 = click.prompt("Enter the first domain:", default="https://www.gsa.gov")
    d2 = click.prompt("Enter the second domain:", default="https://gsa-test-d10.gsa-ecas.cloud")
    folder = click.prompt("Enter folder name:", default="report")
    os.makedirs(f'./{folder}/', mode = 0o755, exist_ok = True)

    comparer.setup(folder = f'./{folder}/', browser=browser, debug=False)

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
                p1,
                p2
            )
            #break

    comparer.create_report_end()
    comparer.shutdown()