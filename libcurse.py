#!/usr/bin/python3

from bs4 import BeautifulSoup, SoupStrainer
from abc import ABC, abstractmethod
import threading

import requests
import time
import cfscrape

class CurseCatalogScraper(ABC):
    def __init__(self):
        self._catalog_length = 1
        self._catalogTable = []

        self._maxthreads = 50
        self.sem = threading.BoundedSemaphore(self._maxthreads)

        self.mutex = threading.Lock()

    @abstractmethod
    def open(self, url):
        raise NotImplementedError

    def setMaxThreads(self, threads):
        self._maxthreads = threads
        self.sem = threading.BoundedSemaphore(self._maxthreads)

    def getCatalogPage(self, page):
        response = self.open(CurseURL().catalog_page(page))

        return response.text

    def getCatalogLength(self):
        soup = BeautifulSoup(self.getCatalogPage(1), "lxml")

        pager = soup.find_all(class_="pagination-item")
        if pager:
            return int(pager[-1].text)
        else:
            raise Exception("Could not determine number of pages in catalog");

    def getCatalog(self):
        self._catalogTable.clear()

        self._catalog_length = self.getCatalogLength()

        threads = [threading.Thread(target=self.__threading_parseCatalogPage, args=(page,)) for page in range(1, self._catalog_length+1)]

        for t in threads:
            self.sem.acquire()
            t.start()

        for t in threads:
            t.join()

        return self._catalogTable

    def __parseCatalogPage(self, page):
        text = self.getCatalogPage(page)

        strainer = SoupStrainer(class_="my-2")

        soup = BeautifulSoup(text, "lxml", parse_only=strainer)

        self.mutex.acquire()
        projects = soup.select(".project-listing-row")

        for project in projects:
            r = {}

            link = project.find_all("a")[1]

            r['name']= link.text.replace('\\r','').replace('\\n','').strip()
            r['curse_id'] = link['href'].split('/')[-1]

            self._catalogTable.append(r)

        self.mutex.release()

    def __threading_parseCatalogPage(self, page):
        self.__parseCatalogPage(page)
        self.sem.release()
    
class CurseReleaseScraper(ABC):
    def __init__(self, curse_id, major):
        self.curse_id = curse_id
        self.major = major
        self.__getReleaseTable()

    def __getReleaseTable(self):
        releaseTable = []

        try:
            url = CurseURL().files_url(self.curse_id)

            response = self.open(url)
            html = response.text

            soup = BeautifulSoup(html, "lxml")
            lis = soup.find("table", {'class':'project-file-listing'}).find("tbody").findAll("tr")

            for row in lis:
                r = {}

                cols = row.find_all("td")
                link = cols[1].find("a")

                r['release_type'] = cols[0].text.strip()
                r['version'] = link.text.strip()
                r['curse_id'] = self.curse_id
                r['release_id'] = link['href'].split('/')[-1]
                r['size'] = cols[2].text.strip()
                r['upload_date'] = cols[3].text.strip()
                r['game_version'] = cols[4].text.strip().split()[0]

                releaseTable.append(r)
        except requests.HTTPError as e:
            print("Curse Update Exception", e)
        except Exception as e:
            print(e)

        self._releaseTable = releaseTable

    def __parseGameVersion(self, game_version):
        major = game_version[0]

        return {'major': major}

    def latestRelease(self):
        for r in self._releaseTable:
            if self.__parseGameVersion(r['game_version'])['major'] == self.major:
                return r

    def latestStableRelease(self):
        for r in self._releaseTable:
            if r['release_type'] == "R" and self.__parseGameVersion(r['game_version'])['major'] == self.major:
                return r

    @abstractmethod
    def open(self, url):
        raise NotImplementedError

class CurseURL:
    __singleton = None

    def __new__(cls, *args, **kwargs):  
        if not cls.__singleton:  
            cls.__singleton = super().__new__(cls)

        return cls.__singleton

    def download_url(self, release):
        return "{}/download/{}".format(self.addon_url(release['curse_id']), release['release_id'])

    def catalog_page(self, page):
        return "https://www.curseforge.com/wow/addons?page={}".format(page)

    def addon_url(self, curse_id):
        return "https://www.curseforge.com/wow/addons/{}".format(curse_id)

    def curseid_from_addon_url(self, addon_url):
        return addon_url.split('/')[-1]

    def files_url(self, curse_id):
        return "{}/files".format(self.addon_url(curse_id))

    def domain(self):
        return "curseforge.com"

class reference_Opener:  
    __singleton = None
   
    def __new__(cls, *args, **kwargs):  
        if not cls.__singleton:  
            cls.__singleton = super().__new__(cls)

        return cls.__singleton
   
    def open(self, url):  
        count = 0
        maxcount = 5
    
        scraper = cfscrape.CloudflareScraper()

	# Retry
        while count < maxcount:
            try:
                response = scraper.get(url)

                return response

            except Exception as e:
                print("Could not open '{}', retrying... ({})".format(url, count))

                count = count + 1
                time.sleep(1)

                if count >= maxcount:
                    raise

class reference_CurseCatalogScraper(CurseCatalogScraper):
    def open(self, url):
        return reference_Opener().open(url)
        
class reference_CurseReleaseScraper(CurseReleaseScraper):
    def open(self, url):
        return reference_Opener().open(url)

def main():
    pass

if __name__ == "__main__":
    main()
