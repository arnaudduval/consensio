from version import VERSION

def version(request):
    return {'APP_VERSION': VERSION}