import sys

from setuptools import find_packages, setup

sys.path.insert(0, ".")

import pkg_info  # noqa: E402

setup(
    name="hgcs",
    version=pkg_info.release_version,
    description="HGCS Package",
    long_description="""This package contains HGCS components""",
    license="GPL",
    author="FaHui Lin , Harvester group",
    author_email="atlas-adc-harvester-central-support@cern.ch",
    url="https://github.com/PanDAWMS/HGCS",
    python_requires=">=3.6",
    packages=find_packages(where="lib"),
    package_dir={"": "lib"},
    install_requires=[
        "htcondor >= 10.3.0",
    ],
    # optional pip dependencies
    extras_require={},
    data_files=[
        # config
        (
            "etc/hgcs",
            [
                "temp/hgcs.cfg.template",
            ],
        ),
        # init script
        (
            "etc/systemd/system",
            [
                "temp/hgcs.service.template",
            ],
        ),
        # logrotate
        (
            "etc/logrotate.d",
            [
                "temp/logrotate-hgcs",
            ],
        ),
    ],
    scripts=[
        "bin/hgcs_master.py",
    ],
)
