import os
import re
import time
import requests
import click
import string
from selenium.webdriver.common.by import By
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from inspect import getmembers, isfunction
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

if __name__ == "__main__":
    baseDir = './load/';

    title = click.prompt("Enter a title:", default="CDN Sites")
    site1 = click.prompt("Enter the first domain:", default="https://www.gsa.gov")
    site2 = click.prompt("Enter the second domain:", default="https://www-gsa-stg-d10.gsa-ecas.cloud")
    #title = click.prompt("Enter a title:", default="Origin Sites")
    #site1 = click.prompt("Enter the first domain:", default="https://origin-www.gsa.gov")
    #site2 = click.prompt("Enter the second domain:", default="https://gsa-stg-d10.gsa-ecas.cloud")
    sites = {
        'site1': {'domain': site1},
        'site2': {'domain': site2},
    };
    times = {
        #'Redirect':     "pageNav['redirectEnd'] - pageNav['redirectStart']",
        #'DNS':          "pageNav['domainLookupEnd'] - pageNav['domainLookupStart']",
        #'TCP':          "pageNav['connectEnd'] - pageNav['connectStart']",
        #'Request':      "pageNav['responseStart'] - pageNav['requestStart']",
        #'Response':     "pageNav['responseEnd'] - pageNav['responseStart']",
        #'Processing':   "pageNav['loadEventStart'] - pageNav['domLoading']",

        'frontend':      "pageNav['responseStart'] - pageNav['navigationStart']",
        'backend':       "pageNav['domComplete'] - pageNav['responseStart']",
        #'Load':          "pageNav['loadEventEnd'] - pageNav['loadEventStart']",
        'total':        "pageNav['loadEventEnd'] - pageNav['navigationStart']",
    };


    ff_options = webdriver.FirefoxOptions()
    ff_options.add_argument("--headless")
    driver = webdriver.Firefox(options=ff_options)

    with open(f'{baseDir}report.html', "w") as file:
        span = len(times)
        file.write('<!DOCTYPE html>\n<head>\n')
        file.write('<link rel="stylesheet" href="//cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">\n')
        file.write('<script src="https://code.jquery.com/jquery-1.12.4.min.js" integrity="sha256-ZosEbRLbNQzLpnKIkEdrPv7lOy9C27hHQ+Xp8a4MxAQ=" crossorigin="anonymous"></script>\n')
        file.write('<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>\n')
        file.write("<script>$(document).ready( function () {$('#myTable').DataTable({paging: false, order: [[9, 'desc']]});} );</script>\n");
        file.write("<style>.n{}.site1{background-color:tomato}.site2{background-color:antiquewhite}.d{background-color:deepskyblue;}</style>\n");
        file.write('</head>\n')
        file.write(f'<h1>{title}</h1>\n');
        file.write('<body>\n');
        file.write('<table class="stripe hover compact" id="myTable">\n')

        file.write('<thead>\n')
        file.write(f'<tr><th rowspan="2" class="n" style="width:25%">path</th><th colspan="{span}" class="site1" style="width:25%">{site1}</th><th colspan="{span}" class="site2" style="width:25%">{site2}</th><th colspan="{span}" class="d" style="width:25%">Diff</th></tr>\n')
        file.write(f'<tr>')
        for key in sites:
            for time in times:
                file.write(f'<th class="{key} {time}">{time}</th>')
        for time in times:
            file.write(f'<th class="d {time}">{time}</th>')
        file.write(f'</tr>\n')
        file.write('</thead>\n')
        file.write('<tbody>\n')

    with open('paths.txt') as f:
        count = len(f.readlines())
    x = 0
    with open('paths.txt') as f:
        for line in f:
            x = x+1
            path = f"{line}".replace("\n", "").replace("\r", "")
            name = re.sub('.+/', '', path)
            print(f"Comparing ({x} of {count}): {path}")

            with open(f'{baseDir}report.html', "a") as file:
                for key in sites:
                    url = f"{sites[key]['domain']}{path}"
                    sites[key]['status_code'] = requests.get(url).status_code
                    driver.get(url)
                    driver.refresh()
                    #WebDriverWait(driver, 5).until(
                    #    EC.all_of(
                    #        EC.presence_of_element_located((By.ID, "main-content")),
                    #        EC.presence_of_element_located((By.ID, "ZN_0d171YnFuvpJle6")),
                    #    )
                    #)

                    pageNav = driver.execute_script("return window.performance.timing;")
                    #print(f"pageNav: {pageNav}")
                    for time in times:
                        sites[key][time] = eval(times[time]);

                file.write(f'<tr title="{path}">')
                file.write(f'<td class="n">{name}</td>')
                for key in sites:
                    for time in times:
                        file.write(f'<td class="{key} {time}">{sites[key][time]}</td>')
                for time in times:
                    total = round(sites['site2'][time] - sites['site1'][time], 0)
                    file.write(f'<td class="d {time}">{total}</td>')
                file.write(f'</tr>\n')
                #empty sites so we don't bleed in case of error setting values
                sites = {
                    'site1': {'domain': site1},
                    'site2': {'domain': site2},
                };
            #break;

    with open(f'{baseDir}report.html', "a") as file:
        file.write("</tbody></table>\r\n</body>\r\n")
    driver.quit();