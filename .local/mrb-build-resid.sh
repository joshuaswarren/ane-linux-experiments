#!/usr/bin/env bash
# MesaRegressionBisect: detached makepkg for the resid-bundle package.
cd /home/joshuawarren/src/mesa-pkg-jw16-resid-20260919 || exit 2
{
  date -Is
  makepkg -s -C -f --noconfirm
  echo "EXIT=$?"
  date -Is
} > /home/joshuawarren/log/jw16-mesa-resid-build.log 2>&1
