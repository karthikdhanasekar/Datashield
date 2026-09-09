import Link from 'next/link'
import { Shield, Search, Eye, FileText, Bell, Lock, ArrowRight, CheckCircle } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-navy-950 cyber-bg overflow-hidden">
      {/* Navigation */}
      <nav className="border-b border-white/10 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-navy-950" />
            </div>
            <span className="text-xl font-bold text-white">DataShield <span className="text-cyan-400">OSINT</span></span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/auth/login" className="text-gray-400 hover:text-white transition-colors text-sm">
              Sign In
            </Link>
            <Link
              href="/auth/register"
              className="bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 py-24 text-center">
        <div className="inline-flex items-center gap-2 bg-cyan-500/10 border border-cyan-500/30 rounded-full px-4 py-2 text-sm text-cyan-400 mb-8">
          <Shield className="w-4 h-4" />
          <span>Ethical OSINT · Privacy First · GDPR Compliant</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
          <span className="text-white">Is Your Data</span>
          <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
            Exposed Online?
          </span>
        </h1>

        <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          DataShield OSINT discovers your exposed personal information across the internet,
          generates removal requests, and monitors your digital footprint continuously.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/auth/register"
            className="flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold px-8 py-4 rounded-xl text-lg transition-all glow-cyan"
          >
            Scan Your Data Now
            <ArrowRight className="w-5 h-5" />
          </Link>
          <Link
            href="#features"
            className="flex items-center gap-2 border border-white/20 hover:border-cyan-500/50 text-white px-8 py-4 rounded-xl text-lg transition-colors"
          >
            Learn More
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-8 mt-20 max-w-2xl mx-auto">
          {[
            { value: '10M+', label: 'Breach Records Monitored' },
            { value: '95%', label: 'Removal Success Rate' },
            { value: '24/7', label: 'Continuous Monitoring' },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl font-black text-cyan-400">{stat.value}</div>
              <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-white mb-4">Complete Privacy Protection</h2>
          <p className="text-gray-400 text-lg">Everything you need to find, remove, and monitor your exposed data</p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <div key={feature.title} className="glass-card p-6 hover:border-cyan-500/30 transition-colors group">
              <div className="w-12 h-12 bg-cyan-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-cyan-500/20 transition-colors">
                <feature.icon className="w-6 h-6 text-cyan-400" />
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">{feature.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-white mb-4">How It Works</h2>
        </div>
        <div className="grid md:grid-cols-4 gap-8">
          {steps.map((step, i) => (
            <div key={step.title} className="text-center">
              <div className="w-12 h-12 bg-cyan-500 text-navy-950 font-black text-xl rounded-full flex items-center justify-center mx-auto mb-4">
                {i + 1}
              </div>
              <h3 className="text-white font-semibold mb-2">{step.title}</h3>
              <p className="text-gray-400 text-sm">{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Legal/Ethics callout */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <div className="glass-card p-8 border-cyan-500/20">
          <div className="flex items-start gap-4">
            <Lock className="w-8 h-8 text-cyan-400 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-white font-bold text-xl mb-3">Ethical & Legal OSINT Only</h3>
              <p className="text-gray-400 leading-relaxed mb-4">
                DataShield OSINT performs <strong className="text-white">consent-based</strong> investigation using only
                publicly available information. We strictly follow GDPR, privacy laws, and responsible disclosure practices.
                We never perform hacking, unauthorized access, or illegal data collection.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {['GDPR Compliant', 'OWASP Secure', 'No Unauthorized Access',
                  'Encrypted Data', 'Rate Limited', 'Audit Logged'].map((badge) => (
                  <div key={badge} className="flex items-center gap-2 text-sm text-green-400">
                    <CheckCircle className="w-4 h-4" />
                    {badge}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <h2 className="text-4xl font-bold text-white mb-6">Take Control of Your Privacy</h2>
        <p className="text-gray-400 mb-10 text-lg">Join thousands protecting their digital identity with DataShield OSINT</p>
        <Link
          href="/auth/register"
          className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold px-10 py-5 rounded-xl text-xl transition-all glow-cyan"
        >
          Start Free Scan <ArrowRight className="w-6 h-6" />
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 px-6 py-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-sm text-gray-500">
          <span>© 2024 DataShield OSINT. Privacy Protection Platform.</span>
          <div className="flex gap-6">
            <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

const features = [
  {
    icon: Search,
    title: 'Personal Data Scanner',
    description: 'Scan email, phone, name, username, Aadhaar, PAN, and passport for exposures across the internet.',
  },
  {
    icon: Shield,
    title: 'Breach Monitoring',
    description: 'Check HaveIBeenPwned and public breach databases for your email and credentials.',
  },
  {
    icon: Eye,
    title: 'Social Media Detection',
    description: 'Discover public profile exposures on GitHub, Reddit, Twitter, LinkedIn and more.',
  },
  {
    icon: FileText,
    title: 'Takedown Requests',
    description: 'Auto-generate GDPR, Right to Be Forgotten, and privacy removal requests.',
  },
  {
    icon: Bell,
    title: 'Continuous Monitoring',
    description: 'Daily, weekly, or monthly monitoring with instant alerts when data reappears.',
  },
  {
    icon: Lock,
    title: 'Evidence Reports',
    description: 'Export evidence packages as PDF, JSON, or CSV for legal use.',
  },
]

const steps = [
  { title: 'Enter Your Data', description: 'Provide the personal info you want to scan — email, name, phone, etc.' },
  { title: 'OSINT Scan', description: 'Our engine searches search engines, breach databases, and social platforms.' },
  { title: 'Review Findings', description: 'Get a detailed report with severity ratings and exposure evidence.' },
  { title: 'Take Action', description: 'Send removal requests and monitor until your data is gone.' },
]
