%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_ver: %define python_ver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name: tuna
Version: 0.2
Release: 1%{?dist}
License: GPLv2
Summary: Application tuning GUI & command line utility
Group: Application/System
Source: http://userweb.kernel.org/~acme/tuna/%{name}-%{version}.tar.bz2
BuildArch: noarch
BuildRequires: python-devel
Requires: python-ethtool
Requires: python-linux-procfs
Requires: python-schedutils
BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

%description
Provides interface for changing scheduler and IRQ tunables, at whole CPU and at per
thread/IRQ level. Allows isolating CPUs for use by a specific application and moving
threads and interrupts to a CPU by just dragging and dropping them.

Can be used as a command line utility without requiring the GUI libraries to be
installed.

%prep
%setup -q -c -n %{name}-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
mkdir -p %{buildroot}/{%{_bindir},%{_datadir}/tuna/help/kthreads}
install -m644 tuna/tuna_gui.glade %{buildroot}/%{_datadir}/tuna/
install -m755 tuna-cmd.py %{buildroot}/%{_bindir}/tuna
install -m644 help/kthreads/* %{buildroot}/%{_datadir}/tuna/help/kthreads/

%clean
rm -rf %{buildroot}

%files
%defattr(0755,root,root,0755)
%{_bindir}/tuna
%dir %{_datadir}/tuna/
%{_datadir}/tuna/tuna_gui.glade
%dir %{_datadir}/tuna/help
%dir %{_datadir}/tuna/help/kthreads/
%{_datadir}/tuna/help/kthreads/*
%{python_sitelib}/tuna/
%if "%{python_ver}" >= "2.5"
%{python_sitelib}/*.egg-info
%endif

%changelog
* Thu Mar 27 2008 Arnaldo Carvalho de Melo <acme@redhat.com> - 0.2-1
- Command line interface
- Remove the requirement of a GUI packages
- Allow moving one child thread to a CPU
- Status icon
- "What is this?", for now just for some kernel threads
- Add "Restore CPU" to undo "Isolate CPU"
- Faster CPU isolation process
- Allow moving IRQs & Threads to all cpus
- CPU filtering

* Mon Feb 26 2008 Arnaldo Carvalho de Melo <acme@redhat.com> - 0.1-1
- package created
