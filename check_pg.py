import psycopg2,yaml
cfg=yaml.safe_load(open(chr(99)+chr(111)+chr(110)+chr(102)+chr(105)+chr(103)+chr(47)+chr(115)+chr(101)+chr(116)+chr(116)+chr(105)+chr(110)+chr(103)+chr(115)+chr(46)+chr(121)+chr(97)+chr(109)+chr(108)))
pg=cfg[chr(112)+chr(111)+chr(115)+chr(116)+chr(103)+chr(114)+chr(101)+chr(115)]
conn=psycopg2.connect(host=pg[chr(104)+chr(111)+chr(115)+chr(116)],port=pg[chr(112)+chr(111)+chr(114)+chr(116)],dbname=pg[chr(100)+chr(97)+chr(116)+chr(97)+chr(98)+chr(97)+chr(115)+chr(101)],user=pg[chr(117)+chr(115)+chr(101)+chr(114)],password=pg[chr(112)+chr(97)+chr(115)+chr(115)+chr(119)+chr(111)+chr(114)+chr(100)])
cur=conn.cursor()
cur.execute(chr(83)+chr(69)+chr(76)+chr(69)+chr(67)+chr(84)+chr(32)+chr(115)+chr(111)+chr(117)+chr(114)+chr(99)+chr(101)+chr(44)+chr(116)+chr(97)+chr(114)+chr(103)+chr(101)+chr(116)+chr(32)+chr(70)+chr(82)+chr(79)+chr(77)+chr(32)+chr(114)+chr(111)+chr(97)+chr(100)+chr(95)+chr(101)+chr(100)+chr(103)+chr(101)+chr(115)+chr(32)+chr(76)+chr(73)+chr(77)+chr(73)+chr(84)+chr(32)+chr(50))
print(cur.fetchall())
