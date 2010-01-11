#! /usr/bin/env python

# -*- coding: utf-8 -*-

import os
import sys
import getopt
import urllib
import re
import tempfile
import shutil
import subprocess

# validate CLI arguments and start downloading
def main(argv):
    if not findInPath("pdftk"):
        error("You have to install pdftk.")
    if not findInPath("iconv"):
        error("You have to install iconv.")

    try:
        opts, args = getopt.getopt(argv, "hl:c:", ["help", "link=","content="])
    except getopt.GetoptError:
        error()

    link = ""

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-c", "--content"):
            if link != "":
                error("-c and -l arguments are mutually exclusive")

            link = "http://springerlink.com/content/" + arg
        elif opt in ("-l", "--link"):
            if link != "":
                error("-c and -l arguments are mutually exclusive")

            link = arg

    if link == "":
        error("You have to define a link.")
    if not re.match("https?://(www\.)?springerlink.(com|de)/content/[a-z0-9\-]+(/\?[^/]*)?$", link):
        error("Bad link given. See LINK below.")

    # remove all arguments from link
    link = re.sub(r"/?\?[^/]*$", "/", link)

    #make sure the link ends on a slash
    if link[-1] != "/":
      link += "/"

    baseLink = link

    chapters = list()
    hasFrontMatter = False
    hasBackMatter = False

    loader = urllib.FancyURLopener()

    bookTitle = ""

    while True:
        # download page source
        try:
            print "Please wait, link source is being downloaded...\n\t%s" % link
            page = loader.open(link).read()
        except IOError, e:
            error("Bad link given (%s)" % e)

        if bookTitle == "":
            match = re.search(r'<h2 class="MPReader_Profiles_SpringerLink_Content_PrimitiveHeadingControlName">([^<]+)</h2>', page)
            if not match or match.group(1).strip() == "":
                error("Could not evaluate book title - bad link?")
            else:
                bookTitle = match.group(1).strip()
            print "\nThe book you are trying to download is called '%s'\n" % bookTitle


        # get chapters
        for match in re.finditer('href="([^"]+.pdf)"', page):
            chapterLink = match.group(1)
            if chapterLink == "back-matter.pdf":
                hasBackMatter = True
                continue
            if chapterLink == "front-matter.pdf":
                hasFrontMatter = True
                continue
            if chapterLink[:7] == "http://":
                continue
            chapters.append(chapterLink)

        # get next page
        match = re.search(r'<a href="([^"]+)">Next</a>', page)
        if match:
            link = "http://springerlink.com" + match.group(1).replace("&amp;", "&")
        else:
            break

    if hasFrontMatter:
        chapters.insert(0, "front-matter.pdf")

    if hasBackMatter:
        chapters.append("back-matter.pdf")

    if len(chapters) == 0:
        error("No chapters found - bad link?")

    print "found %d chapters" % len(chapters)

    # setup
    curDir = os.getcwd()
    tempDir = tempfile.mkdtemp()
    os.chdir(tempDir)

    i = 1
    fileList = list()

    for chapterLink in chapters:
        if chapterLink[0] == "/":
            chapterLink = "http://springerlink.com" + chapterLink
        else:
            chapterLink = baseLink + chapterLink

        print "downloading chapter %d/%d" % (i, len(chapters))
        localFile, mimeType = geturl(chapterLink, "%d.pdf" % i)

        if mimeType.gettype() != "application/pdf":
            os.chdir(curDir)
            shutil.rmtree(tempDir)
            error("downloaded chapter %s has invalid mime type %s - are you allowed to download it?" % (chapterLink, mimeType.gettype()))

        fileList.append(localFile)
        i += 1

    print "merging chapters"

    p1 = subprocess.Popen(["echo", bookTitle], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["iconv", "-f", "UTF-8", "-t" ,"ASCII//TRANSLIT"], stdin=p1.stdout, stdout=subprocess.PIPE)
    bookTitlePath = p2.communicate()[0]
    bookTitlePath = bookTitlePath.strip()
    if bookTitlePath == "":
        os.chdir(curDir)
        shutil.rmtree(tempDir)
        error("could not transliterate book title %s" % bookTitle)

    bookTitlePath = bookTitlePath.replace("/", "-")
    bookTitlePath = re.sub("\s+", "_", bookTitlePath)

    bookTitlePath = curDir + "/%s.pdf" % bookTitlePath

    if len(fileList) == 1:
      shutil.move(fileList[0], bookTitlePath)
    else:
      os.system("pdftk %s cat output '%s'" % (" ".join(fileList), bookTitlePath))

    # cleanup
    os.chdir(curDir)
    shutil.rmtree(tempDir)

    print "book %s was successfully downloaded, it was saved to %s" % (bookTitle, bookTitlePath)

    sys.exit()

# give a usage message
def usage():
    print """Usage:
%s [OPTIONS]

Options:
  -h, --help              Display this usage message
  -l LINK, --link=LINK    defines the link of the book you intend to download
  -c HASH, --content=HASH builds the link from a given HASH (see below)

You have to set exactly one of these options.

LINK:
  The link to your the detail page of the ebook of your choice on SpringerLink.
  It lists book metadata and has a possibly paginated list of the chapters of the book.
  It has the form:
    http://springerlink.com/content/HASH/STUFF
  Where: HASH is a string consisting of lower-case, latin chars and numbers.
         It alone identifies the book you intent do download.
         STUFF is optional and looks like ?p=...&p_o=... or similar. Will be stripped.
""" % os.path.basename(sys.argv[0])

# raise an error and quit
def error(msg=""):
    if msg != "":
        print "\nERROR: %s\n" % msg
    usage()
    sys.exit(2)

    return None

# based on http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def findInPath(prog):
    for path in os.environ["PATH"].split(os.pathsep):
        exe_file = os.path.join(path, prog)
        if os.path.exists(exe_file) and os.access(exe_file, os.X_OK):
            return True
    return False

# based on http://mail.python.org/pipermail/python-list/2005-April/319818.html
def _reporthook(numblocks, blocksize, filesize, url=None):
    #XXX Should handle possible filesize=-1.
    try:
        percent = min((numblocks*blocksize*100)/filesize, 100)
    except:
        percent = 100
    if numblocks != 0:
        sys.stdout.write("\b"*70)
    sys.stdout.write("%-66s%3d%%" % (url, percent))

def geturl(url, dst):
    if sys.stdout.isatty():
        response = urllib.urlretrieve(url, dst,
                           lambda nb, bs, fs, url=url: _reporthook(nb,bs,fs,url))
        sys.stdout.write("\n")
    else:
        response = urllib.urlretrieve(url, dst)

    return response


# start program
if __name__ == "__main__":
    main(sys.argv[1:])
