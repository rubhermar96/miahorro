"""Bank statement importers (RF-IMP-01, RF-IMP-07).

Pure code with no database: read a file into a table, find the columns and turn each row into
a dated, signed amount. Each format is independent (RNF-12): a broken reader only affects the
files it reads.
"""
