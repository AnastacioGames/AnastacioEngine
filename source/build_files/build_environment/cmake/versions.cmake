# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENSE BLOCK *****

set(ZLIB_VERSION 1.2.12)
set(ZLIB_URI https://zlib.net/zlib-${ZLIB_VERSION}.tar.gz)
set(ZLIB_HASH 5fc414a9726be31427b440b434d05f78)

set(OPENAL_VERSION 1.18.2)
set(OPENAL_URI http://openal-soft.org/openal-releases/openal-soft-${OPENAL_VERSION}.tar.bz2)
set(OPENAL_HASH a936806ebd8de417b0ffd8cf3f48f456)

set(PNG_VERSION 1.6.37)
set(PNG_URI http://prdownloads.sourceforge.net/libpng/libpng-${PNG_VERSION}.tar.xz)
set(PNG_HASH 505e70834d35383537b6491e7ae8641f1a4bed1876dbfe361201fc80868d88ca)

set(JPEG_VERSION 2.1.3)
set(JPEG_URI https://github.com/libjpeg-turbo/libjpeg-turbo/archive/${JPEG_VERSION}.tar.gz)
set(JPEG_HASH 627b980fad0573e08e4c3b80b290fc91)

set(BOOST_VERSION 1.78.0)
set(BOOST_VERSION_SHORT 1.78)
set(BOOST_VERSION_NODOTS 1_78_0)
set(BOOST_VERSION_NODOTS_SHORT 1_78)
set(BOOST_URI https://dl.bintray.com/boostorg/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_NODOTS}.tar.gz)
set(BOOST_HASH c2f6428ac52b0e5a3c9b2e1d8cc832b5)

set(BLOSC_VERSION 1.21.1)
set(BLOSC_URI https://github.com/Blosc/c-blosc/archive/v${BLOSC_VERSION}.tar.gz)
set(BLOSC_HASH 134b55813b1dca57019d2a2dc1f7a923)

set(PTHREADS_VERSION 3.0.0)
set(PTHREADS_URI http://sourceforge.mirrorservice.org/p/pt/pthreads4w/pthreads4w-code-v${PTHREADS_VERSION}.zip)
set(PTHREADS_HASH f3bf81bb395840b3446197bcf4ecd653)

set(OPENEXR_VERSION 3.1.4)
set(OPENEXR_URI https://github.com/AcademySoftwareFoundation/openexr/archive/v${OPENEXR_VERSION}.tar.gz)
set(OPENEXR_HASH e990be1ff765797bc2d93a8060e1c1f2)

set(IMATH_VERSION 3.1.4)
set(IMATH_URI https://github.com/AcademySoftwareFoundation/Imath/archive/v${OPENEXR_VERSION}.tar.gz)
set(IMATH_HASH fddf14ec73e12c34e74c3c175e311a3f)
set(IMATH_HASH_TYPE MD5)
set(IMATH_FILE imath-${IMATH_VERSION}.tar.gz)

if (WIN32)
	# Openexr started appending _d on its own so now
	# we need to tell the build the postfix is _s while
	# telling all other deps the postfix is _s_d
	if(BUILD_MODE STREQUAL Release)
		set(OPENEXR_VERSION_POSTFIX _s)
		set(OPENEXR_VERSION_BUILD_POSTFIX _s)
	else()
		set(OPENEXR_VERSION_POSTFIX _s_d)
		set(OPENEXR_VERSION_BUILD_POSTFIX _s)
	endif()
else()
	set(OPENEXR_VERSION_BUILD_POSTFIX)
	set(OPENEXR_VERSION_POSTFIX)
endif()

set(FREETYPE_VERSION 2.9.1)
set(FREETYPE_URI http://prdownloads.sourceforge.net/freetype/freetype-${FREETYPE_VERSION}.tar.gz)
set(FREETYPE_HASH 3adb0e35d3c100c456357345ccfa8056)

set(GLEW_VERSION 1.13.0)
set(GLEW_URI http://prdownloads.sourceforge.net/glew/glew/${GLEW_VERSION}/glew-${GLEW_VERSION}.tgz)
set(GLEW_HASH 7cbada3166d2aadfc4169c4283701066)

set(FREEGLUT_VERSION 3.0.0)
set(FREEGLUT_URI http://pilotfiber.dl.sourceforge.net/project/freeglut/freeglut/${FREEGLUT_VERSION}/freeglut-${FREEGLUT_VERSION}.tar.gz)
set(FREEGLUT_HASH 90c3ca4dd9d51cf32276bc5344ec9754)

set(HDF5_VERSION 1.8.17)
set(HDF5_URI https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8/hdf5-${HDF5_VERSION}/src/hdf5-${HDF5_VERSION}.tar.gz)
set(HDF5_HASH 7d572f8f3b798a628b8245af0391a0ca)

set(ALEMBIC_VERSION 1.8.3)
set(ALEMBIC_URI https://github.com/alembic/alembic/archive/${ALEMBIC_VERSION}.tar.gz)
set(ALEMBIC_MD5 2cd8d6e5a3ac4a014e24a4b04f4fadf9)

## hash is for 3.1.2
set(GLFW_GIT_UID 30306e54705c3adae9fe082c816a3be71963485c)
set(GLFW_URI https://github.com/glfw/glfw/archive/${GLFW_GIT_UID}.zip)
set(GLFW_HASH 20cacb1613da7eeb092f3ac4f6b2b3d0)

#latest uid in git as of 2016-04-01
set(CLEW_GIT_UID 277db43f6cafe8b27c6f1055f69dc67da4aeb299)
set(CLEW_URI https://github.com/OpenCLWrangler/clew/archive/${CLEW_GIT_UID}.zip)
set(CLEW_HASH 2c699d10ed78362e71f56fae2a4c5f98)

#latest uid in git as of 2016-04-01
set(CUEW_GIT_UID 1744972026de9cf27c8a7dc39cf39cd83d5f922f)
set(CUEW_URI https://github.com/CudaWrangler/cuew/archive/${CUEW_GIT_UID}.zip)
set(CUEW_HASH 86760d62978ebfd96cd93f5aa1abaf4a)

set(OPENSUBDIV_VERSION v3_4_0_RC2)
set(OPENSUBDIV_Hash f6a10ba9efaa82fde86fe65aad346319)
set(OPENSUBDIV_URI https://github.com/PixarAnimationStudios/OpenSubdiv/archive/${OPENSUBDIV_VERSION}.tar.gz)

set(SDL_VERSION 2.0.20)
set(SDL_URI https://www.libsdl.org/release/SDL2-${SDL_VERSION}.tar.gz)
set(SDL_HASH a53acc02e1cca98c4123229069b67c9e)

set(OPENCOLLADA_VERSION v1.6.68)
set(OPENCOLLADA_URI https://github.com/KhronosGroup/OpenCOLLADA/archive/${OPENCOLLADA_VERSION}.tar.gz)
set(OPENCOLLADA_HASH ee7dae874019fea7be11613d07567493)

set(OPENCOLORIO_VERSION 1.1.1)
set(OPENCOLORIO_URI https://github.com/AcademySoftwareFoundation/OpenColorIO/archive/v${OPENCOLORIO_VERSION}.tar.gz)
set(OPENCOLORIO_HASH 23d8b9ac81599305539a5a8674b94a3d)

set(LLVM_VERSION 12.0.0)
set(LLVM_URI https://github.com/llvm/llvm-project/releases/download/llvmorg-${LLVM_VERSION}/llvm-project-${LLVM_VERSION}.src.tar.xz)
set(LLVM_HASH 5a4fab4d7fc84aefffb118ac2c8a4fc0)
set(LLVM_HASH_TYPE MD5)
set(LLVM_FILE llvm-project-${LLVM_VERSION}.src.tar.xz)

set(OPENMP_URI https://github.com/llvm/llvm-project/releases/download/llvmorg-${LLVM_VERSION}/openmp-${LLVM_VERSION}.src.tar.xz)
set(OPENMP_HASH ac48ce3e4582ccb82f81ab59eb3fc9dc)
set(OPENMP_HASH_TYPE MD5)
set(OPENMP_FILE openmp-${LLVM_VERSION}.src.tar.xz)

set(OPENIMAGEIO_VERSION v2.3.13.0)
set(OPENIMAGEIO_URI https://github.com/OpenImageIO/oiio/archive/refs/tags/${OPENIMAGEIO_VERSION}.tar.gz)
set(OPENIMAGEIO_HASH de45fb38501c4581062b522b53b6141c)

# 8.0.0 is currently oiio's preferred vesion although never versions may be available.
# the preferred version can be found in oiio's externalpackages.cmake
set(FMT_VERSION 8.0.0)
set(FMT_URI https://github.com/fmtlib/fmt/archive/refs/tags/${FMT_VERSION}.tar.gz)
set(FMT_HASH 7bce0e9e022e586b178b150002e7c2339994e3c2bbe44027e9abb0d60f9cce83)
set(FMT_HASH_TYPE SHA256)
set(FMT_FILE fmt-${FMT_VERSION}.tar.gz)

# 0.6.2 is currently oiio's preferred vesion although never versions may be available.
# the preferred version can be found in oiio's externalpackages.cmake
set(ROBINMAP_VERSION v0.6.2)
set(ROBINMAP_URI https://github.com/Tessil/robin-map/archive/refs/tags/${ROBINMAP_VERSION}.tar.gz)
set(ROBINMAP_HASH c08ec4b1bf1c85eb0d6432244a6a89862229da1cb834f3f90fba8dc35d8c8ef1)
set(ROBINMAP_HASH_TYPE SHA256)
set(ROBINMAP_FILE robinmap-${ROBINMAP_VERSION}.tar.gz)

set(TIFF_VERSION 4.3.0)
set(TIFF_URI http://download.osgeo.org/libtiff/tiff-${TIFF_VERSION}.tar.gz)
set(TIFF_HASH 0a2e4744d1426a8fc8211c0cdbc3a1b3)

set(OSL_VERSION 1.11.17.0)
set(OSL_URI https://github.com/imageworks/OpenShadingLanguage/archive/Release-${OSL_VERSION}.tar.gz)
set(OSL_HASH 63265472ce14548839ace2e21e401544)

set(PYTHON_VERSION 3.10.2)
set(PYTHON_SHORT_VERSION 3.10)
set(PYTHON_SHORT_VERSION_NO_DOTS 310)
set(PYTHON_URI https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz)
set(PYTHON_HASH 14e8c22458ed7779a1957b26cde01db9)

set(TBB_VERSION 2020_U3)
set(TBB_URI https://github.com/01org/tbb/archive/${TBB_VERSION}.tar.gz)
set(TBB_HASH 55ec8df6eae5ed6364a47f0e671e460c)

set(OPENVDB_VERSION 9.0.0)
set(OPENVDB_URI https://github.com/dreamworksanimation/openvdb/archive/v${OPENVDB_VERSION}.tar.gz)
set(OPENVDB_HASH 684ce40c2f74f3a0c9cac530e1c7b07e)

set(IDNA_VERSION 3.3)
set(CHARSET_NORMALIZER_VERSION 2.0.10)
set(URLLIB3_VERSION 1.26.8)
set(CERTIFI_VERSION 2021.10.8)
set(REQUESTS_VERSION 2.27.1)

set(NUMPY_VERSION v1.23.5)
set(NUMPY_SHORT_VERSION 1.23)
set(NUMPY_URI https://github.com/numpy/numpy/releases/download/v${NUMPY_VERSION}/numpy-${NUMPY_VERSION}.tar.gz)
set(NUMPY_HASH 8b2692a511a3795f3af8af2cd7566a15)

set(LAME_VERSION 3.100)
set(LAME_URI http://downloads.sourceforge.net/project/lame/lame/3.100/lame-${LAME_VERSION}.tar.gz)
set(LAME_HASH 83e260acbe4389b54fe08e0bdbf7cddb)

set(OGG_VERSION 1.3.5)
set(OGG_URI http://downloads.xiph.org/releases/ogg/libogg-${OGG_VERSION}.tar.gz)
set(OGG_HASH 0eb4b4b9420a0f51db142ba3f9c64b333f826532dc0f48c6410ae51f4799b664)

set(VORBIS_VERSION 1.3.7)
set(VORBIS_URI http://downloads.xiph.org/releases/vorbis/libvorbis-${VORBIS_VERSION}.tar.gz)
set(VORBIS_HASH 0e982409a9c3fc82ee06e08205b1355e5c6aa4c36bca58146ef399621b0ce5ab)

set(THEORA_VERSION 1.1.1)
set(THEORA_URI http://downloads.xiph.org/releases/theora/libtheora-${THEORA_VERSION}.tar.bz2)
set(THEORA_HASH b6ae1ee2fa3d42ac489287d3ec34c5885730b1296f0801ae577a35193d3affbc)

set(FLAC_VERSION 1.3.4)
set(FLAC_URI http://downloads.xiph.org/releases/flac/flac-${FLAC_VERSION}.tar.xz)
set(FLAC_HASH 8ff0607e75a322dd7cd6ec48f4f225471404ae2730d0ea945127b1355155e737 )

set(VPX_VERSION 1.11.0)
set(VPX_URI https://github.com/webmproject/libvpx/archive/v${VPX_VERSION}/libvpx-v${VPX_VERSION}.tar.gz)
set(VPX_HASH 965e51c91ad9851e2337aebcc0f517440c637c506f3a03948062e3d5ea129a83)

set(OPUS_VERSION 1.3.1)
set(OPUS_URI https://archive.mozilla.org/pub/opus/opus-${OPUS_VERSION}.tar.gz)
set(OPUS_HASH 65b58e1e25b2a114157014736a3d9dfeaad8d41be1c8179866f144a2fb44ff9d)

set(X264_URI https://code.videolan.org/videolan/x264/-/archive/master/x264-33f9e1474613f59392be5ab6a7e7abf60fa63622.tar.gz)
set(X264_HASH 300dfb5b6c35722516f168868ce9419252a9e9eb77a05d82c9cede925b691bd6)

set(XVIDCORE_VERSION 1.3.7)
set(XVIDCORE_URI http://downloads.xvid.org/downloads/xvidcore-${XVIDCORE_VERSION}.tar.gz)
set(XVIDCORE_HASH 165ba6a2a447a8375f7b06db5a3c91810181f2898166e7c8137401d7fc894cf0)

set(OPENJPEG_VERSION 2.4.0)
set(OPENJPEG_SHORT_VERSION 2.4)
set(OPENJPEG_URI https://github.com/uclouvain/openjpeg/archive/v${OPENJPEG_VERSION}.tar.gz)
set(OPENJPEG_HASH 8702ba68b442657f11aaeb2b338443ca8d5fb95b0d845757968a7be31ef7f16d)

set(FFMPEG_VERSION 4.0.2)
set(FFMPEG_URI http://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.bz2)
set(FFMPEG_HASH 5576e8a22f80b6a336db39808f427cfb)

set(FFTW_VERSION 3.3.10)
set(FFTW_URI http://www.fftw.org/fftw-${FFTW_VERSION}.tar.gz)
set(FFTW_HASH 8ccbf6a5ea78a16dbc3e1306e234cc5c)

set(ICONV_VERSION 1.15)
set(ICONV_URI http://ftp.gnu.org/pub/gnu/libiconv/libiconv-${ICONV_VERSION}.tar.gz)
set(ICONV_HASH ace8b5f2db42f7b3b3057585e80d9808)

set(LAPACK_VERSION 3.6.0)
set(LAPACK_URI http://www.netlib.org/lapack/lapack-${LAPACK_VERSION}.tgz)
set(LAPACK_HASH f2f6c67134e851fe189bb3ca1fbb5101)

set(LIBSNDFILE_VERSION 1.0.28)
set(LIBSNDFILE_URI http://www.mega-nerd.com/libsndfile/files/libsndfile-${LIBSNDFILE_VERSION}.tar.gz)
set(LIBSNDFILE_HASH 646b5f98ce89ac60cdb060fcd398247c)

#set(HIDAPI_VERSION 0.8.0-rc1)
#set(HIDAPI_URI https://github.com/signal11/hidapi/archive/hidapi-${HIDAPI_VERSION}.tar.gz)
#set(HIDAPI_HASH 069f9dd746edc37b6b6d0e3656f47199)

set(HIDAPI_UID 89a6c75dc6f45ecabd4ddfbd2bf5ba6ad8ba38b5)
set(HIDAPI_URI https://github.com/TheOnlyJoey/hidapi/archive/${HIDAPI_UID}.zip)
set(HIDAPI_HASH b6e22f6b514f8bcf594989f20ffc46fb)

set(WEBP_VERSION 1.2.2)
set(WEBP_URI https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-${WEBP_VERSION}.tar.gz)
set(WEBP_HASH b5e2e414a8adee4c25fe56b18dd9c549)

set(SPNAV_VERSION 0.2.3)
set(SPNAV_URI http://downloads.sourceforge.net/project/spacenav/spacenav%20library%20%28SDK%29/libspnav%20${SPNAV_VERSION}/libspnav-${SPNAV_VERSION}.tar.gz)
set(SPNAV_HASH 44d840540d53326d4a119c0f1aa7bf0a)

set(JEMALLOC_VERSION 5.0.1)
set(JEMALLOC_URI https://github.com/jemalloc/jemalloc/releases/download/${JEMALLOC_VERSION}/jemalloc-${JEMALLOC_VERSION}.tar.bz2)
set(JEMALLOC_HASH 507f7b6b882d868730d644510491d18f)

set(XML2_VERSION 2.9.4)
set(XML2_URI http://xmlsoft.org/sources/libxml2-${XML2_VERSION}.tar.gz)
set(XML2_HASH ae249165c173b1ff386ee8ad676815f5)

set(TINYXML_VERSION 2_6_2)
set(TINYXML_VERSION_DOTS 2.6.2)
set(TINYXML_URI https://nchc.dl.sourceforge.net/project/tinyxml/tinyxml/${TINYXML_VERSION_DOTS}/tinyxml_${TINYXML_VERSION}.tar.gz)
set(TINYXML_HASH c1b864c96804a10526540c664ade67f0)

set(YAMLCPP_VERSION 0.6.3)
set(YAMLCPP_URI https://codeload.github.com/jbeder/yaml-cpp/tar.gz/yaml-cpp-${YAMLCPP_VERSION})
set(YAMLCPP_HASH b45bf1089a382e81f6b661062c10d0c2)

set(PYSTRING_VERSION v1.1.3)
set(PYSTRING_URI https://codeload.github.com/imageworks/pystring/tar.gz/refs/tags/${PYSTRING_VERSION})
set(PYSTRING_HASH f2c68786b359f5e4e62bed53bc4fb86d)
set(PYSTRING_HASH_TYPE MD5)
set(PYSTRING_FILE pystring-${PYSTRING_VERSION}.tar.gz)

set(LCMS_VERSION 2.9)
set(LCMS_URI https://nchc.dl.sourceforge.net/project/lcms/lcms/${LCMS_VERSION}/lcms2-${LCMS_VERSION}.tar.gz)
set(LCMS_HASH 8de1b7724f578d2995c8fdfa35c3ad0e)

set(PUGIXML_VERSION 1.10)
set(PUGIXML_URI https://github.com/zeux/pugixml/archive/v${PUGIXML_VERSION}.tar.gz)
set(PUGIXML_HASH 0c208b0664c7fb822bf1b49ad035e8fd)

set(FLEXBISON_VERSION 2.5.5) # RanGE: 2.5.24 -> see c5e5ac4
set(FLEXBISON_URI http://prdownloads.sourceforge.net/winflexbison//win_flex_bison-2.5.5.zip)
set(FLEXBISON_HASH d87a3938194520d904013abef3df10ce)

# Libraries to keep Python modules static on Linux.

# NOTE: bzip.org domain does no longer belong to BZip 2 project, so we download
# sources from Debian packaging.
set(BZIP2_VERSION 1.0.6)
set(BZIP2_URI http://http.debian.net/debian/pool/main/b/bzip2/bzip2_${BZIP2_VERSION}.orig.tar.bz2)
set(BZIP2_HASH d70a9ccd8bdf47e302d96c69fecd54925f45d9c7b966bb4ef5f56b770960afa7)

set(FFI_VERSION 3.2.1)
set(FFI_URI https://sourceware.org/pub/libffi/libffi-${FFI_VERSION}.tar.gz)
set(FFI_HASH d06ebb8e1d9a22d19e38d63fdb83954253f39bedc5d46232a05645685722ca37)

set(LZMA_VERSION 5.2.4)
set(LZMA_URI https://tukaani.org/xz/xz-${LZMA_VERSION}.tar.bz2)
set(LZMA_HASH 3313fd2a95f43d88e44264e6b015e7d03053e681860b0d5d3f9baca79c57b7bf)

set(SSL_VERSION 1.1.0i)
set(SSL_URI https://www.openssl.org/source/openssl-${SSL_VERSION}.tar.gz)
set(SSL_HASH ebbfc844a8c8cc0ea5dc10b86c9ce97f401837f3fa08c17b2cdadc118253cf99)

set(SQLITE_VERSION 3.24.0)
set(SQLITE_URI https://www.sqlite.org/2018/sqlite-src-3240000.zip)
set(SQLITE_HASH fb558c49ee21a837713c4f1e7e413309aabdd9c7)

set(EMBREE_VERSION 3.13.3)
set(EMBREE_URI https://github.com/embree/embree/archive/v${EMBREE_VERSION}.zip)
set(EMBREE_HASH f62766ba54e48a2f327c3a22596e7133)

set(OIDN_VERSION 1.0.0)
set(OIDN_URI https://github.com/OpenImageDenoise/oidn/releases/download/v${OIDN_VERSION}/oidn-${OIDN_VERSION}.src.zip)
set(OIDN_HASH 19fe67b0164e8f020ac8a4f520defe60)

set(LEVEL_ZERO_VERSION v1.7.15)
set(LEVEL_ZERO_URI https://github.com/oneapi-src/level-zero/archive/refs/tags/${LEVEL_ZERO_VERSION}.tar.gz)
set(LEVEL_ZERO_HASH c39bb05a8e5898aa6c444e1704105b93d3f1888b9c333f8e7e73825ffbfb2617)
set(LEVEL_ZERO_HASH_TYPE SHA256)
set(LEVEL_ZERO_FILE level-zero-${LEVEL_ZERO_VERSION}.tar.gz)