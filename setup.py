import sys
from setuptools import setup, find_packages
from . import pkg_info

sys.path.insert(0, '.')


setup(
    name='HGCS',
    version=pkg_info.release_version,
    description='HGCS Package',
    long_description='''This package contains HGCS components''',
    license='GPL',
    author='FaHui Lin , Harvester group',
    author_email='atlas-adc-harvester-central-support@cern.ch',
    url='https://github.com/PanDAWMS/HGCS',
    python_requires='>=3.6',
    packages=find_packages(),
    install_requires=[
                      'htcondor >= 8.9.0',
                      ],

    # optional pip dependencies
    extras_require={
        },

    data_files=[
            # config
            ('etc/hgcs', ['temp/hgcs.cfg.template',
                            ]
                ),
            # init script
            ('etc/systemd/system', ['temp/hgcs.service.template',
                                    ]
                ),
            # logrotate
            ('etc/logrotate.d', ['temp/logrotate-hgcs',
                                ]
                ),
        ],

    scripts=['bin/hgcs.py',
             ]
    )
