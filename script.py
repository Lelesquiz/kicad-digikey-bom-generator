# coding=utf-8

import sys
import requests
from bs4 import BeautifulSoup
import unicodecsv
import re
import os
import argparse
import os


class Componente():

    def __init__(self):
        self.digikey_link = ""

    def __str__(self):
        return "{}, {}, {}, {}".format(self.reference, self.value, self.footprint, self.digikey_link)

    def parsa(self, linea):
        if linea[0] == "L":
            self.name = linea.split(" ")[1]
            self.reference = linea.split(" ")[2]
        if linea[0] == "U":
            self.N = linea.split(" ")[1]
            self.mm = linea.split(" ")[2]
            self.timestamp = linea.split(" ")[3]
        if linea[0] == "P":
            self.pos_x = linea.split(" ")[1]
            self.pos_y = linea.split(" ")[1]
        if linea[0] == "F":
            n = int(linea.split(" ")[1])
            if n == 0:
                self.reference = re.findall(r'"(.*?)"', linea)[0]
            if n == 1:
                self.value = re.findall(r'"(.*?)"', linea)[0]
            if n == 2:
                self.footprint = re.findall(r'"(.*?)"', linea)[0]
            if n == 3:
                self.link = re.findall(r'"(.*?)"', linea)[0]
            if n == 4:
                self.digikey_link = re.findall(r'"(.*?)"', linea)[0]

    def is_power(self):
        if self.reference[0] == "#":
            return True
        return False


class Board():
    def __init__(self, filename):
        self.filename = os.path.abspath(filename)
        self.sheets = self.get_sheets()
        self.componenti = self.get_componenti()

    def get_sheets(self):
        with open(self.filename, "r") as f:
            linee = f.readlines()
        in_sheet = False
        lista_sheets = [self.filename]
        for linea in linee:
            if linea.strip() == "$Sheet":
                in_sheet = True
            if linea.strip() == "$EndSheet":
                in_sheet = False
            if in_sheet and linea.split(" ")[0] == "F1":
                matches = re.findall(r'\"(.+?)\"', linea)
                abs_path = os.path.join(os.path.dirname(self.filename), matches[0])
                lista_sheets.append(abs_path)
        return lista_sheets

    def get_componenti(self):
        componenti = []
        lines = []
        for sheet in self.sheets:
            try:
                with open(sheet, "r") as f:
                    lines += f.readlines()
            except Exception as e:
                print(e)
        componente = None
        while len(lines):
            linea = lines[0].strip()
            if linea == "$Comp":
                componente = Componente()
            elif linea == "$EndComp":
                componenti.append(componente)
                componente = None
            elif componente:
                componente.parsa(linea)
            lines.pop(0)
        return componenti

    def get_componenti_bom(self):
        return [componente for componente in self.componenti if not componente.is_power()]

    def get_componenti_senza_footprint(self):
        return [componente for componente in self.get_componenti_bom() if componente.footprint == ""]

    def get_componenti_con_footprint(self):
        return [componente for componente in self.get_componenti_bom() if componente.footprint != ""]

    def get_componenti_senza_link_digikey(self):
        return [componente for componente in self.get_componenti_bom() if "digikey" not in componente.digikey_link]

    def get_righe_bom(self):
        d = {}
        for componente in self.get_componenti_bom():
            #k = componente.name, componente.value, componente.footprint, componente.digikey_link
            k = "", componente.value, componente.footprint, componente.digikey_link
            if k not in d:
                d[k] = []
            d[k].append(componente)
        return d.items()

    def crea_bom(self, out_file):
        print()
        numero_riga = 1
        filename = out_file
        with open(filename, 'wb') as f:
            writer = unicodecsv.writer(f, delimiter=';', quotechar='"')
            row = ["ID", "REFERENCE", "VALORE", "FOOTPRINT", "NUMERO COMPONENTI", "DESCRIZIONE", "PRODUTTORE", "CODICE PRODUTTORE",
                   "CODICE DIGIKEY", "QUANTITÀ DISPONIBILE", "DESCRIZIONE DETTAGLIATA"]
            row += [""] * 20
            row += ["DIGIKEY LINK", "DATASHEET LINK"]
            writer.writerow(row)
            for (k, componenti) in self.get_righe_bom():
                row = []
                lista_reference = [c.reference for c in componenti]
                value = componenti[0].value
                footprint = componenti[0].footprint
                digikey_link = componenti[0].digikey_link
                print("\nRow number {}:".format(numero_riga))
                print_tabular("value", value)
                print_tabular("footprint", footprint)
                print_tabular("digikey link", digikey_link)
                print_tabular("refs", " ".join(lista_reference))
                row.append(numero_riga)
                row.append(",".join([componente.reference for componente in componenti]))
                row.append(k[1])
                row.append(k[2])
                row.append(len(componenti))
                link = k[3]
                if "digikey" in link:
                    infos = get_digikey_infos(link)
                    print_tabular("manufacturer part number", infos.MPN())
                    print_tabular("digikey code", infos.codice())
                    print_tabular("manufacturer", infos.manufacturer())
                    print_tabular("description", infos.description())
                    print_tabular("available quantity", infos.quantita_disponibile())
                    print_tabular("detailed description", infos.detailed_description())
                    print_tabular("price table", infos.price_table())
                    print_tabular("datasheet", infos.datasheet())
                    row.append(infos.description())
                    row.append(infos.manufacturer())
                    row.append(infos.MPN())
                    row.append(infos.codice())
                    row.append(infos.quantita_disponibile())
                    row.append(infos.detailed_description())
                    for qty, prezzo in infos.price_table():
                        if qty != "":
                            row.append("Costo per {}".format(qty))
                            row.append(prezzo)
                        else:
                            row.append("")
                            row.append("")
                    row.append(link)
                    row.append(infos.datasheet())
                writer.writerow(row)
                numero_riga += 1


def print_tabular(s1, s2):
    print("{: <60}{}".format("  - {}:".format(s1), s2))


class DigikeyInfo():

    def __init__(self, link):
        self.link = link
        self.html = requests.get(link).text
        self.soup = BeautifulSoup(self.html, 'html.parser')

    def codice(self):
        i = self.soup.find("td", {"id": "reportPartNumber"})
        if i:
            return i.text.strip()
        return "codice non trovato"

    def quantita_disponibile(self):
        i = self.soup.find("td", {"id": "quantityAvailable"})
        if i:
            return i.text.strip().split("\n")[0].strip().replace(".", "")
        return "quantità disponibile non trovata"

    def manufacturer(self):
        i = self.soup.find("h2", {"itemprop": "manufacturer"})
        if i:
            return i.text.strip()
        return "manufacturer non trovato"

    def MPN(self):
        i = self.soup.find("h1", {"itemprop": "model"})
        if i:
            return i.text.strip()
        return "MPN non trovata"

    def description(self):
        i = self.soup.find("td", {"itemprop": "description"})
        if i:
            return i.text.strip()
        return "descrizione non trovata"

    def detailed_description(self):
        i = self.soup.find("h3", {"itemprop": "description"})
        if i:
            return i.text.strip()
        return "descrizione dettagliata non trovata"

    def price_table(self):
        try:
            table = self.soup.find("table", {"id": "product-dollars"})
            prezzi = []
            for row in table.find_all("tr")[1:]:
                qty = row.find_all("td")[0].text.strip().replace(".", "")
                prezzo = float(row.find_all("td")[2].text.strip().replace(
                    ".", "").replace(",", ".").replace("€", ""))
                prezzi.append((qty, prezzo))
            while len(prezzi) < 10:
                prezzi.append(("", ""))
            return prezzi
        except Exception as e:
            raise
            return (("?", "?"), ("?", "?"), ("?", "?"), ("?", "?"), ("?", "?"))

    def datasheet(self):
        try:
            link = self.soup.find("a", {"class": "lnkDatasheet"})["href"]
            if link[:5] != "https":
                link = "https:" + link
            return link
        except Exception:
            return ""


def get_digikey_infos(link):
    info = DigikeyInfo(link)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("schematic_file", help="Schematic file (.sch) from which to generate the BOM")
    parser.add_argument("bom_output_file", help="BOM output file (.csv) to generate")
    args = parser.parse_args()
    print("\nUsing \"{}\" as schematic file".format(os.path.abspath(args.schematic_file)))
    board = Board(os.path.abspath(args.schematic_file))
    print("\nThe BOM components will be taken from the following files:")
    for sheet in sorted(board.get_sheets()):
        print("  - {}".format(os.path.basename(sheet)))
    print("\nFound a total of {} components".format(len(board.get_componenti_bom())))
    print("{} have no footprint".format(len(board.get_componenti_senza_footprint())))
    if len(board.get_componenti_senza_footprint()):
        for comp in board.get_componenti_senza_footprint():
            print("  - {} {}".format(comp.reference, comp.value))
    print("{} have no digikey link".format(len(board.get_componenti_senza_link_digikey())))
    if len(board.get_componenti_senza_link_digikey()):
        for comp in board.get_componenti_senza_link_digikey():
            print("  - {} {}".format(comp.reference, comp.value))
    board.crea_bom(out_file=args.bom_output_file)


if __name__ == '__main__':
    main()
