%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_ver: %define python_ver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name: tuna
Version: 0.9
Release: 2%{?dist}
License: GPLv2
Summary: Application tuning GUI & command line utility
Group: Applications/System
Source: http://userweb.kernel.org/~acme/tuna/%{name}-%{version}.tar.bz2
URL: http://userweb.kernel.org/~acme/tuna/
BuildArch: noarch
BuildRequires: python-devel, gettext
Requires: python-ethtool
Requires: python-linux-procfs >= 0.4.2
Requires: python-schedutils >= 0.2
# This really should be a Suggests...
# Requires: python-inet_diag
BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

%description
Provides interface for changing scheduler and IRQ tunables, at whole CPU and at
per thread/IRQ level. Allows isolating CPUs for use by a specific application
and moving threads and interrupts to a CPU by just dragging and dropping them.
Operations can be done on CPU sockets, understanding CPU topology.

Can be used as a command line utility without requiring the GUI libraries to be
installed.

%package -n oscilloscope
Summary: Generic Oscilloscope
Group: Applications/System
Requires: python-matplotlib
Requires: python-numeric
Requires: pygtk2
Requires: tuna = %{version}-%{release}

%description -n oscilloscope
Plots stream of values read from standard input on the screen together with
statistics and a histogram.

Allows to instantly see how a signal generator, such as cyclictest, signaltest
or even ping, reacts when, for instance, its scheduling policy or real time
priority is changed, be it using tuna or plain chrt & taskset.

%prep
%setup -q

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
mkdir -p %{buildroot}/{%{_bindir},%{_datadir}/tuna/help/kthreads}
install -p -m644 tuna/tuna_gui.glade %{buildroot}/%{_datadir}/tuna/
install -p -m755 tuna-cmd.py %{buildroot}/%{_bindir}/tuna
install -p -m755 oscilloscope-cmd.py %{buildroot}/%{_bindir}/oscilloscope
install -p -m644 help/kthreads/* %{buildroot}/%{_datadir}/tuna/help/kthreads/

# l10n-ed message catalogues
for lng in `cat po/LINGUAS`; do
        po=po/"$lng.po"
        mkdir -p %{buildroot}/%{_datadir}/locale/${lng}/LC_MESSAGES
        msgfmt $po -o %{buildroot}/%{_datadir}/locale/${lng}/LC_MESSAGES/%{name}.mo
done

%find_lang %name

%clean
rm -rf %{buildroot}

%files -f %{name}.lang
%defattr(-,root,root,-)
%doc ChangeLog
%if "%{python_ver}" >= "2.5"
%{python_sitelib}/*.egg-info
%endif
%{_bindir}/tuna
%{_datadir}/tuna/
%{python_sitelib}/tuna/

%files -n oscilloscope
%defattr(-,root,root,-)
%{_bindir}/oscilloscope
%doc docs/oscilloscope+tuna.html
%doc docs/oscilloscope+tuna.pdf

%changelog
* Mon Aug 17 2009 Arnaldo Carvalho de Melo <acme@redhat.com> - 0.9-2
- Use install -p
- Add BuildRequires for gettext

* Fri Jul 10 2009 Arnaldo Carvalho de Melo <acme@redhat.com> - 0.9-1
- Fedora package reviewing changes: introduce ChangeLog file
