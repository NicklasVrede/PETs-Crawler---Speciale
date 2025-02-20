import csv

# The data as a list of tuples (rank, domain)
sites = [
    (1, "Amazon.co.uk"), (21, "Www.gov.uk"), (41, "Royalmail.com"), (61, "Rightmove.co.uk"), (81, "Virginmedia.com"),
    (2, "Theguardian.com"), (22, "Express.co.uk"), (42, "Aruba.it"), (62, "Tnt.com"), (82, "Currys.co.uk"),
    (3, "Bbc.co.uk"), (23, "Euronews.com"), (43, "United.com"), (63, "Theoutnet.com"), (83, "Topshop.com"),
    (4, "Who.int"), (24, "Oup.com"), (44, "Next.co.uk"), (64, "Selfridges.com"), (84, "Chrono24.com"),
    (5, "Google.co.uk"), (25, "Search.yahoo.com"), (45, "Bt.com"), (65, "Johnlewis.com"), (85, "Itv.com"),
    (6, "Webex.com"), (26, "Eset.com"), (46, "Rte.ie"), (66, "Thetimes.co.uk"), (86, "Quidco.com"),
    (7, "Edition.cnn.com"), (27, "Britishcouncil.org"), (47, "Tesco.com"), (67, "Fxstreet.com"), (87, "Easyjet.com"),
    (8, "Dailymail.co.uk"), (28, "Sky.com"), (48, "Newsnow.co.uk"), (68, "Dailystar.co.uk"), (88, "Hsbc.com"),
    (9, "Rt.com"), (29, "Sap.com"), (49, "Voanews.com"), (69, "Asda.com"), (89, "Sainsburys.co.uk"),
    (10, "Asos.com"), (30, "Mirror.co.uk"), (50, "Childrensalon.com"), (70, "Ucas.com"), (90, "Riverisland.com"),
    (11, "Cambridge.org"), (31, "Weforum.org"), (51, "Thelancet.com"), (71, "Here.com"), (91, "Macworld.co.uk"),
    (12, "Ebay.co.uk"), (32, "Metro.co.uk"), (52, "Babyshop.com"), (72, "Standard.co.uk"), (92, "Serif.com"),
    (13, "Reuters.com"), (33, "News.sky.com"), (53, "Argos.co.uk"), (73, "Wipo.int"), (93, "Harveynichols.com"),
    (14, "Bet365.com"), (34, "Jdsports.co.uk"), (54, "Skysports.com"), (74, "Gumtree.com"), (94, "Yougov.com"),
    (15, "Dw.com"), (35, "Ubs.com"), (55, "Channel4.com"), (75, "Brownsfashion.com"), (95, "Aeroflot.ru"),
    (16, "Hm.com"), (36, "Economist.com"), (56, "Ryanair.com"), (76, "Prnewswire.com"), (96, "Nme.com"),
    (17, "Ft.com"), (37, "Espncricinfo.com"), (57, "Irishtimes.com"), (77, "Newscientist.com"), (97, "Active.com"),
    (18, "Telegraph.co.uk"), (38, "Thomann.de"), (58, "Advfn.com"), (78, "Radiotimes.com"), (98, "Indeed.co.uk"),
    (19, "Independent.co.uk"), (39, "Cosmopolitan.com"), (59, "Siemens.com"), (79, "Hotukdeals.com"), (99, "Meltwater.com"),
    (20, "Thesun.co.uk"), (40, "Nhs.uk"), (60, "Lyst.co.uk"), (80, "Harrods.com"), (100, "Nokia.com")
]

# Sort sites by rank
sites.sort(key=lambda x: x[0])

# Write to CSV
with open('data/study-sites.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['rank', 'domain'])  # header
    writer.writerows(sites)

print("Created study-sites.csv with 100 websites")

# Print some statistics
tlds = {}
for _, domain in sites:
    tld = domain.split('.')[-1]
    if tld not in tlds:
        tlds[tld] = 0
    tlds[tld] += 1

print("\nTLD distribution:")
for tld, count in sorted(tlds.items()):
    print(f".{tld}: {count} sites")

# Print first 10 sites to verify sorting
print("\nFirst 10 sites:")
for rank, domain in sites[:10]:
    print(f"{rank}. {domain}") 