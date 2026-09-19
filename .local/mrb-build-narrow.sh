#!/usr/bin/env bash
# MesaRegressionBisect: two narrowing package builds, sequential, niced.
set -u
build_one() {
  local dir=$1 log=$2
  cd "$dir" || return 9
  {
    date -Is
    nice -n 10 makepkg -s -C -f --noconfirm
    echo "EXIT=$?"
    date -Is
  } > "$log" 2>&1
  echo "$dir EXIT=$?"
}
R=/home/joshuawarren/src
rm -rf "$R/mesa-pkg-jw16-noftz-20260919" "$R/mesa-pkg-jw16-nod8f-20260919"
cp -a "$R/mesa-pkg-jw16-resid-20260919" "$R/mesa-pkg-jw16-noftz-20260919"
cp -a "$R/mesa-pkg-jw16-resid-20260919" "$R/mesa-pkg-jw16-nod8f-20260919"
sed -i 's/^_commit=.*/_commit=e1677564284be72c663a65afeb6fd1d22cf45c17/; s/^pkgrel=.*/pkgrel=1/' "$R/mesa-pkg-jw16-noftz-20260919/PKGBUILD"
sed -i 's/^_commit=.*/_commit=d447b649a94d408f3008c476a5e1f9ddcec8115f/; s/^pkgrel=.*/pkgrel=1/' "$R/mesa-pkg-jw16-nod8f-20260919/PKGBUILD"
build_one "$R/mesa-pkg-jw16-noftz-20260919" /home/joshuawarren/log/jw16-mesa-noftz-build.log
build_one "$R/mesa-pkg-jw16-nod8f-20260919" /home/joshuawarren/log/jw16-mesa-nod8f-build.log
echo ALL-BUILDS-DONE
