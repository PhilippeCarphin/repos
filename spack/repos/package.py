# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# ----------------------------------------------------------------------------
# If you submit this package back to Spack as a pull request,
# please first remove this boilerplate and all FIXME comments.
#
# This is a template package file for Spack.  We've put "FIXME"
# next to all the things you'll want to change. Once you've handled
# them, you can save this file and test your package like this:
#
#     spack install repos
#
# You can edit this file again by typing:
#
#     spack edit repos
#
# See the Spack documentation for more information on packaging.
# ----------------------------------------------------------------------------

from spack.package import *


class Repos(CMakePackage):
    """Helper tools for managing repositories"""

    homepage = "https://gitlab.com/philippecarphin/repos"
    git = "https://gitlab.com/philippecarphin/repos.git"

    maintainers("philippecarphin")

    license("UNKNOWN", checked_by="philippecarphin")

    version("1.7.0")

    depends_on("go", type="build")
    depends_on("pandoc", type="build")
    depends_on("python@3.8:", type="run")
    depends_on("py-pyyaml", type="run")
