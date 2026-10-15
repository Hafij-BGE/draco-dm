# RPM recipe for Fedora (and other dnf-based distros with the same package names). Built by packaging/linux/build-rpm.sh.
%global __brp_python_bytecompile %{nil}

Name:           draco-dm
Version:        %{draco_version}
Release:        1%{?dist}
Summary:        Fast multi-connection download manager
License:        GPL-3.0-or-later
URL:            https://github.com/Hafij-BGE/draco-dm
BuildArch:      noarch

Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       gobject-introspection
Recommends:     yt-dlp
Recommends:     (ffmpeg or ffmpeg-free)

%description
Draco speeds up downloads by splitting files across up to 32 connections, resumes
broken downloads, captures downloads and videos from the browser (Chrome, Edge,
Brave, Firefox), downloads HLS streams with subtitles, and runs queues on a schedule.
Includes a site grabber, batch downloads, a speed limiter and 14 themes.

%install
sh %{draco_src}/packaging/linux/stage.sh %{buildroot} %{_prefix}

%files
%{_bindir}/draco
%{_prefix}/lib/draco
%{_datadir}/applications/io.github.draco.DracoDM.desktop
%{_datadir}/metainfo/io.github.draco.DracoDM.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/io.github.draco.DracoDM.png
%{_datadir}/doc/draco-dm
%{_datadir}/licenses/draco-dm

%changelog
* Thu Oct 15 2026 Md Hafijur Rahman <draco@localhost> - 1.4.4-1
- Theme names no longer use other products' names

* Thu Oct 15 2026 Md Hafijur Rahman <draco@localhost> - 1.4.3-1
- Release 1.4.3
