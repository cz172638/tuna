%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: tuna
Version: 0.1
Release: 1%{?dist}
License: GPLv2
Summary: Application tuning GUI
Group: Application/System
Source: http://userweb.kernel.org/~acme/python-linux-procfs/%{name}-%{version}.tar.bz2
BuildArch: noarch
BuildRequires: python-devel
Requires: pygtk2
Requires: pygtk2-libglade
Requires: python-ethtool
Requires: python-linux-procfs
Requires: python-schedutils
BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

%description
Provides interface for changing scheduler and IRQ tunables, at whole CPU and at per
thread/IRQ level. Allows isolating CPUs for use by a specific application and moving
threads and interrupts to a CPU by just dragging and dropping them.

%prep
%setup -q -c -n %{name}-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
mkdir -p %{buildroot}/{%{_bindir},%{_datadir}/tuna}
install -m644 tuna/tuna_gui.glade %{buildroot}/%{_datadir}/tuna/
install -m755 tuna-cmd.py %{buildroot}/%{_bindir}/tuna

%clean
rm -rf %{buildroot}

%files
%defattr(0755,root,root,0755)
%{_bindir}/tuna
%{_datadir}/tuna
%{_datadir}/tuna/tuna_gui.glade
%{python_sitelib}/tuna/
%{python_sitelib}/*.egg-info

%changelog
* Mon Feb 26 2008 Arnaldo Carvalho de Melo <acme@redhat.com> - 0.1-1
- package created
