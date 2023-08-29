# The previous iteration method used too much memory, but there are some enhancements to improve this:
# https://stackoverflow.com/questions/7171140/using-python-iterparse-for-large-xml-files
# https://stackoverflow.com/questions/12160418/why-is-lxml-etree-iterparse-eating-up-all-my-memory
# https://web.archive.org/web/20210309115224/http://www.ibm.com/developerworks/xml/library/x-hiperfparse/
def fast_iter(context, func, *args, **kwargs):
    """
    http://lxml.de/parsing.html#modifying-the-tree
    Based on Liza Daly's fast_iter
    http://www.ibm.com/developerworks/xml/library/x-hiperfparse/
    See also http://effbot.org/zone/element-iterparse.htm
    """
    for event, element in context:
        func(element, *args, **kwargs)
        # It's safe to call clear() here because no descendants will be accessed
        element.clear()
        # Also eliminate now-empty references from the root node to elem
        for ancestor in element.xpath('ancestor-or-self::*'):
            while ancestor.getprevious() is not None:
                del ancestor.getparent()[0]
    del context
