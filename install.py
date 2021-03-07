# installer GTS
# Copyright 2020 Johanna Roedenbeck
# Distributed under the terms of the GNU Public License (GPLv3)

from weecfg.extension import ExtensionInstaller

def loader():
    return GTSInstaller()

class GTSInstaller(ExtensionInstaller):
    def __init__(self):
        super(GTSInstaller, self).__init__(
            version="0.3",
            name='GTS',
            description='Provides Gruenlandtemperatursumme (GTS), a kind of growing degree days',
            author="Johanna Roedenbeck",
            author_email="",
            xtype_services='user.GTS.GTSService',
            config={
              'StdWXCalculate':{
                'Calculations':{
                  'GTS':'software,archive',
                  'GTSdate':'software,archive',
                  'utcoffsetLMT':'software,archive',
                  'dayET':'software,archive',
                  'ET24':'software,archive'}}},
            files=[('bin/user', ['bin/user/GTS.py'])]
            )
