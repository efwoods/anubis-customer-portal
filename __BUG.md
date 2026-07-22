https://checkout.neuralnexus.site/?checkout=success

Server Not Found

Firefox can’t connect to the server at checkout.neuralnexus.site.
What can you do about it?

Try connecting on a different device. Check your modem or router. Disconnect and reconnect to Wi-Fi.

Learn more…
Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:     172.21.0.1:36418 - "GET /config HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/invoices?customer=cus_UvgJ7VeOXRTUqI&limit=24&expand[0]=data.payment_intent.latest_charge
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:     172.21.0.1:36404 - "GET /billing_info HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:     172.21.0.1:36418 - "GET /me HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1782864000&end_time=1784685660&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/invoices?customer=cus_UvgJ7VeOXRTUqI&limit=24&expand[0]=data.payment_intent.latest_charge response_code=200
portal-server-1  | INFO:     172.21.0.1:36412 - "GET /invoices HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20 response_code=200
portal-server-1  | INFO:     172.21.0.1:36390 - "GET /payment_methods HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1782864000&end_time=1784685660&limit=100 response_code=200
portal-server-1  | INFO:     172.21.0.1:36340 - "GET /usage HTTP/1.1" 200 OK
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:36388 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:36388 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:37000 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     172.21.0.1:33202 - "OPTIONS /subscription/change HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=post url=https://api.stripe.com/v1/checkout/sessions
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/checkout/sessions response_code=200
portal-server-1  | INFO:     172.21.0.1:33202 - "POST /subscription/change HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:51012 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:33426 - "GET /healthz HTTP/1.1" 200 OK


w Enable Watch   d Detach

# BUG 2
Selecting `switch to this plan for premium` triggered `firefox is asking for permissions`: investigate why this occurred please.




    Skip to main content
    Switch language
    Skip to search

Windows 10 reached EOS (end of support) on October 14, 2025. If you are on Windows 10, see this article.
Mozilla Support Logo

    Explore Help Articles
    Community Forums
    Ask a Question
    Contribute

    Sign In/Up

    Home
    Firefox
    Privacy and security
    Control personal device and local...

Ask a Question

Still need help? Sign in to ask your question on our forums.
Continue

        Customize this article
        Firefox

Was this article helpful?
Control personal device and local network permissions in Firefox
Firefox
Last updated:
6/12/26 43% of users voted this helpful

To better protect your privacy and security, Firefox includes permissions that control whether websites can access apps and services on your local network and local device. This change stops websites from exploiting them without your knowledge.

progressive rollout banner This feature is experimental and is being introduced to the Firefox user base through a progressive rollout. It may not yet be available to all users.
This feature is available in Beta and Nightly pre-release versions of Firefox. Starting in Firefox version 149, this feature is enabled for users who have Enhanced Tracking Protection (ETP) set to Strict. It will be gradually rolled out to all Firefox users beginning with Firefox 151. Local network access restrictions will be enabled by default and Firefox will require you to explicitly allow public websites to access local network resources.

Table of Contents

    Why is Firefox adding these permissions?
    What to expect when a site requests access
        What is considered “device apps and services”?
        What is considered a “local network device”?
    Manage access permissions to your device and local network
        Configure access permissions
    Advanced Configuration (about:config)
        To access these preferences
        Available preferences
            network.lna.enabled (boolean)
            network.lna.blocking (boolean)
            network.lna.block_trackers (boolean)
            network.lna.skip-domains (string)
        Troubleshooting and monitoring
        Report issues
    Related articles

Why is Firefox adding these permissions?

Websites can attempt to access your personal device – such as your computer or local network – and connected devices – such as routers, printers and local web servers – without your permission. Malicious sites have used these capabilities to track you or scan for vulnerable devices.

To keep you safe and help you stay in control of your data and devices, Firefox now asks for your permission when a site tries to connect to your device or local network.
What to expect when a site requests access

When a website tries to access your device or local network, Firefox will display a permission prompt similar to those for accessing your camera or microphone.

You can choose to:

    Allow access for that visit
    Block access for that visit 

You can also choose to have Firefox remember your decision for all future visits. You can change it anytime in your Settings.
What is considered “device apps and services”?

“Device apps and services” are your personal computer and all the applications installed on it.
What is considered a “local network device”?

Local network devices are any hardware connected to the same local network as your device. This includes:

    Routers
    Printers
    File servers
    Smart TVs
    Media streamers
    IoT (Internet of Things) devices 

Accessing these devices over the network could allow websites to interact with or retrieve data from them. A permission check helps prevent sites from doing so without your knowledge.
Manage access permissions to your device and local network

When a site tries to access other apps and services on your device or your local network, Firefox will show a permission prompt near the address bar, asking you to allow access.

For Device apps and services, the prompt looks like this:

devicepermissionschanged

For Local network devices, the prompt looks like this:

localnetworkchanges

Tip: If you want Firefox to remember your choice for the site for all future visits, you can also check the Don’t ask again for this site box.
Configure access permissions

    Click the menu button Fx89menuButton and select Settings.
    Go to the Permissions and data panel.
    Scroll down to the Permissions section.
    Find and click the Device apps and services entry.
    Here you’ll see a list of sites that have requested this permission.
    Use the dropdown menu next to each site to change access.
    Find and click the Local network devices entry, and repeat steps 5-6. 

fx152permissionsanddata

For Device apps and services, the Settings dialog looks like this:

deviceservices

For Local network devices, the Settings dialog looks like this:

localnetwork

Advanced Configuration (about:config)

For users who need more control over local network access behavior, Firefox provides advanced preferences accessible through about:config.

Warning: These instructions are for experienced Firefox users. Changing settings in the Configuration Editor (about:config) can have serious effects on your browser’s stability, security and performance.
Only proceed if you are comfortable with advanced settings and understand the potential impacts.

To access these preferences

    Type about:config in the address bar and press Enter.
    A warning page may appear. Click Accept the Risk and Continue to go to the about:config page.

    Fx145aboutconfig

    Search for the preference name you want to modify.
    Double-click to change boolean values (true/false) or click the edit icon for other values. 

Available preferences
network.lna.enabled (boolean)

    Default: true
    Controls whether local network access checks are enforced
    Setting to false disables all local network access restrictions 

network.lna.blocking (boolean)

    Default: true
    Controls the blocking behavior for local network access
    Setting to false allows access without prompts when enabled 

network.lna.block_trackers (boolean)

    Default: false
    Experimental feature that blocks third-party trackers from accessing localhost and local network resources
    Setting to true provides additional protection against tracking scripts 

network.lna.skip-domains (string)

    Default: (empty)
    Comma-separated list of domains that should skip local network access checks
    Can include both source domains (websites making requests) and target domains (local resources being accessed)
    Supports wildcard patterns with *. prefix (for example *.company.com)
    Example: intranet.company.com,*.devices.local 

Troubleshooting and monitoring

If you need to see detailed information about local network access attempts or diagnose issues:

    Press Ctrl + Shift + K to open the Web Console.
    Look for messages related to local network access.
    The console will show which requests were blocked or allowed, helping you understand what’s happening.

    advancedconfiguration

For enterprise environments, administrators can use the LocalNetworkAccess policy to manage these settings organization-wide. See the Firefox Enterprise Policy Documentation for more information.
Report issues

If you encounter unexpected prompts or believe a website is being incorrectly blocked or allowed:

    Open the Web Console to capture relevant error messages (usually starting with Local Network Access…).
    File a bug in Bugzilla under the Core :: Networking component.
    Include in your bug report:
        The website URL where you saw the unexpected prompt
        What you expected to happen vs. what actually happened
        Error messages from the Web Console
        Whether the site is trying to access a local device or local network resource 

Related articles

    Site Permissions panel
    Manage optional permissions for Firefox extensions
    How to manage your camera and microphone permissions with Firefox 


Share this article: https://mzl.la/41ui237

These fine people helped write this article:
AliceWyman, Teo, Mozinet, Paul, Mark Heijl, Denys, Flavius Floare
Illustration of hands
Volunteer

Grow and share your expertise with others. Answer questions and improve our knowledge base.

Learn More
Mozilla
Mozilla

    Report Trademark Abuse
    Source code
    Twitter
    Join our Community
    Explore Help Articles

Firefox

    Download
    Firefox desktop
    Android Browser
    iOS Browser
    Focus Browser

Firefox for Developers

    Developer Edition
    Beta
    Beta for Android
    Nightly
    Nightly for Android

Mozilla Account

    Sign In/Up
    What Is It?
    Reset Password
    Sync Your Data
    Get Help

Language
Language

    Twitter(@firefox)
    YouTube (firefoxchannel)
    Instagram (firefox)

Visit Mozilla Corporation's not-for-profit parent, the Mozilla Foundation.

Portions of this content are ©1998–2026 by individual mozilla.org contributors. Content available under a Creative Commons license.

    mozilla.org Terms of Service Privacy Cookies Contact 

## Local Logs:
e=200
portal-server-1  | INFO:     172.21.0.1:52256 - "GET /usage HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:     172.21.0.1:52242 - "GET /billing_info HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/invoices?customer=cus_UvgJ7VeOXRTUqI&limit=24&expand[0]=data.payment_intent.latest_charge response_code=200
portal-server-1  | INFO:     172.21.0.1:52292 - "GET /invoices HTTP/1.1" 200 OK
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:52244 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20 response_code=200
portal-server-1  | INFO:     172.21.0.1:52270 - "GET /payment_methods HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100 response_code=200
portal-server-1  | INFO:     172.21.0.1:52256 - "GET /usage HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:52244 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685780&limit=100 response_code=200
portal-server-1  | INFO:     172.21.0.1:52292 - "GET /usage HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:44654 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:41118 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:42054 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:54354 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/products?active=true&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/products?active=true&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmIzDQaJBiv2&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmIzDQaJBiv2&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmzW7bhiYboY&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmzW7bhiYboY&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmEAFvahV9lV&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmEAFvahV9lV&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmovQDtYvWHR&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmovQDtYvWHR&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmV9jOTbK5st&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:     127.0.0.1:56546 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmV9jOTbK5st&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmklTlxNxKkd&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmklTlxNxKkd&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmNk0G5kOUUC&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmNk0G5kOUUC&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmxe261w7RUX&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmxe261w7RUX&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmuvj4htuRUW&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmuvj4htuRUW&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/prices?product=prod_UtLmapMRwNdvha&active=true&limit=100&expand[0]=data.tiers
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/prices?product=prod_UtLmapMRwNdvha&active=true&limit=100&expand[0]=data.tiers response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=post url=https://api.stripe.com/v1/subscriptions/sub_1TvpU1Limk9GVblrzsZnxpdy
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions/sub_1TvpU1Limk9GVblrzsZnxpdy response_code=200
portal-server-1  | INFO:     172.21.0.1:54498 - "POST /subscription/change HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:     172.21.0.1:54612 - "GET /config HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/invoices?customer=cus_UvgJ7VeOXRTUqI&limit=24&expand[0]=data.payment_intent.latest_charge
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:     172.21.0.1:54624 - "GET /me HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI response_code=200
portal-server-1  | INFO:     172.21.0.1:54588 - "GET /billing_info HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/invoices?customer=cus_UvgJ7VeOXRTUqI&limit=24&expand[0]=data.payment_intent.latest_charge response_code=200
portal-server-1  | INFO:     172.21.0.1:54600 - "GET /invoices HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgFYffrKDnvEo41Limk9GVblrGbQ/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/customers/cus_UvgJ7VeOXRTUqI/payment_methods?type=card&limit=20 response_code=200
portal-server-1  | INFO:     172.21.0.1:54572 - "GET /payment_methods HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgFYffrKDnvEo41Limk9GVblrGbQ/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgFScg2kbVv2O41Limk9GVblrXWi/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:54506 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgFScg2kbVv2O41Limk9GVblrXWi/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/subscriptions?customer=cus_UvgJ7VeOXRTUqI&status=all&limit=20 response_code=200
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mgEXDOwbrSD9D41Limk9GVblrQqO/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100 response_code=200
portal-server-1  | INFO:stripe:message='Request to Stripe api' method=get url=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100
portal-server-1  | INFO:httpx:HTTP Request: GET https://dev-y3wkm2zfq1qzlef0.us.auth0.com/api/v2/users-by-email?email=epitome_75_springs%40icloud.com "HTTP/1.1 200 OK"
portal-server-1  | INFO:     172.21.0.1:54600 - "GET /subscription HTTP/1.1" 200 OK
portal-server-1  | INFO:stripe:message='Stripe API response' path=https://api.stripe.com/v1/billing/meters/mtr_test_61V0mf0fDHz8iNH3a41Limk9GVblrDFg/event_summaries?customer=cus_UvgJ7VeOXRTUqI&start_time=1784685720&end_time=1784685900&limit=100 response_code=200
portal-server-1  | INFO:     172.21.0.1:54568 - "GET /usage HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:35826 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:52102 - "GET /healthz HTTP/1.1" 200 OK
portal-server-1  | INFO:     127.0.0.1:54576 - "GET /healthz HTTP/1.1" 200 OK


w Enable Watch   d Detach

## BUG 3:
switch to this plan will indicate the subscription switches but will not toggle the currently selected plan:
Switch plan

Upgrades apply immediately (with proration). Downgrades apply at the end of the current billing period — unused allotment continues until then.
Neural Nexus Free Tier — Base Subscription

$0/month

    Messaging tokens: 200,000 tokens/month · $2.00 per 1M over

Neural Nexus Pro Tier — Base Subscription

$20.00/month

30-day free trial

    Document upload tokens: 10,000,000 tokens/month · $3.00 per 1M over
    Messaging tokens: 5,000,000 tokens/month · $1.50 per 1M over

Neural Nexus Premium Tier — Base Subscription

$50.00/month

    Adapter training: 5 units/month · $5.00 per unit over
    Adapter inference tokens: 10,000,000 tokens/month · $4.00 per 1M over
    Document upload tokens: 40,000,000 tokens/month · $2.50 per 1M over
    Messaging tokens: 20,000,000 tokens/month · $1.25 per 1M over

Subscription will end at the period boundary; you will drop to the free tier. Unused allotment continues until then.

Refreshing the page presents no changes; Billing information is not in sync with payment information (billing information should be a stripe element if necessary): 


# BUG
ENABLE PAY PER USE DOES NOT CHANGE THE PAY PER USE STATUS:

curl /verify_subscription_status \
  --header 'Accept: application/json' \
  --header 'API-KEY: sk-OCk2aR1jjs1OtZhcNu2N7EhuD01eG6Hhh_fwsJ68wg8'

{
  "status": "active",
  "tier": "premium",
  "subscription_id": "sub_1TvpU1Limk9GVblrzsZnxpdy",
  "customer_id": "cus_UvgJ7VeOXRTUqI",
  "email": null,
  "pay_per_use_enabled": false,
  "cancel_at_period_end": false,
  "usage_period_start": "2026-07-22T02:12:11+00:00",
  "usage_period_end": "2026-08-22T02:12:11+00:00",
  "meters": {
    "messaging_tokens": {
      "monthly_allotment": 20000000,
      "used_to_date": 0,
      "remaining": 20000000,
      "overage_price_per_million": 1.25,
      "overage_price_per_unit_usd": null
    },
    "document_upload_tokens": {
      "monthly_allotment": 40000000,
      "used_to_date": 0,
      "remaining": 40000000,
      "overage_price_per_million": 2.5,
      "overage_price_per_unit_usd": null
    },
    "adapter_inference_tokens": {
      "monthly_allotment": 10000000,
      "used_to_date": 0,
      "remaining": 10000000,
      "overage_price_per_million": 4.0,
      "overage_price_per_unit_usd": null
    },
    "adapter_training_units": {
      "monthly_allotment": 5,
      "used_to_date": 0,
      "remaining": 5,
      "overage_price_per_million": null,
      "overage_price_per_unit_usd": 5.0
    }
  }


#  I need to know how many free-trial tokens I have used (will match pro-tier message and document usage limits unless the tier changes (during a free-trial; the user retains all pro-tier limits on free-tier and the allotment carries to premium (premium exhausts free-trial usage before premium tier usage; free-trial usage does not carry over to continue an additional month or for duplicate free trials)))
paying for premium then downgrading retains all premium usage until the next billing cycle

I need to know at a glance page-per-use beyond free tier.




# Bug
Messaging tokens are not updating on use or after use:
Usage this period
Jul 22, 2026 – Aug 21, 2026


Free trial: this usage is free up to the full pro-tier allotment shown below.
Document upload tokens0 / 10,000,000 tokens
10,000,000 tokens remaining$3.00 per 1,000,000 tokens over allotment
Messaging tokens0 / 5,000,000 tokens
5,000,000 tokens remaining$1.50 per 1,000,000 tokens over allotment
Pay-per-use past allotment

Requests stop once a meter's monthly allotment is exhausted (HTTP 402).



curl /message/19fd6101-cedb-41e3-a742-3a4d9a555783 \
  --request POST \
  --header 'Accept: application/json' \
  --header 'Content-Type: multipart/form-data' \
  --header 'API-KEY: sk-eNFnpaXdVPYiVTRBhAKBL347p1NHwEiSj2pnzMmS-oQ' \
  --form 'message=test' \
  --form 'your_name=' \
  --form 'your_description=' \
  --form 'conversation_title=' \
  --form 'files=[""]' \
  --form 'thread_id=' \
  --form 'stream=true' \
  --form 'feedback=false' \
  --form 'like=false' \
  --form 'dislike=false' \
  --form 'user_timezone=' \
  --form 'include_quality_metrics=true' \
  --form 'include_usage_metrics=true' \
  --form 'adapter=false'



data: {"type": "usage_estimate", "input_tokens": 20834, "usage": {"meter": "messaging_tokens", "tier": "pro", "monthly_allotment": 5000000, "used_to_date": 0, "remaining": 5000000, "pay_per_use_enabled": false, "usage_period_start": "2026-07-22T14:55:45.330562+00:00", "usage_period_end": "2026-08-22T14:55:45.330562+00:00"}, "thread_id": "48544046-53c7-4fd9-bd24-b30c5c341f95", "request_id": "3687c55e-8233-4004-81a9-f66b24105f0b"}

data: {"type": "assistant_token", "text": "Hey"}

data: {"type": "assistant_token", "text": "\u2014"}

data: {"type": "assistant_token", "text": "what"}

data: {"type": "assistant_token", "text": "\u2019s"}

data: {"type": "assistant_token", "text": " up"}

data: {"type": "assistant_token", "text": "?"}

: keepalive

data: {"type": "done", "content": "Hey\u2014what\u2019s up?", "thread_id": "48544046-53c7-4fd9-bd24-b30c5c341f95", "request_id": "3687c55e-8233-4004-81a9-f66b24105f0b", "total_response_time_ms": 15362, "response_metadata": {"finish_reason": "stop", "model_name": "gpt-5.4-nano-2026-03-17", "service_tier": "default", "model_provider": "openai", "sentiment": {"base_emotion": "neutral", "emotion": "neutral", "score": 0.5597519278526306}, "token_usage": {"prompt_tokens": 21170, "completion_tokens": 9, "total_tokens": 21179}, "features": {"moving_average_ttr": 1.0, "mtld_lexical_diversity": 3.0, "hdd_lexical_diversity": 1.0, "lexical_density_content_word_ratio": 0.5, "noun_density": 0.16666666666666666, "verb_density": 0.3333333333333333, "adjective_density": 0.0, "adverb_density": 0.0, "pronoun_density": 0.16666666666666666, "preposition_density": 0.0, "noun_to_verb_ratio": 0.6666666666666666, "mean_sentence_length_words": 3.0, "stdev_sentence_length_words": 0.0, "interrogative_sentence_ratio": 1.0, "exclamatory_sentence_ratio": 0.0, "comma_rate_per_word": 0.0, "semicolon_rate_per_word": 0.0, "colon_rate_per_word": 0.0, "dash_rate_per_word": 0.3333333333333333, "ellipsis_rate_per_word": 0.0, "exclamation_rate_per_word": 0.0, "question_mark_rate_per_word": 0.3333333333333333, "all_caps_word_ratio": 0.0, "words_per_paragraph": 3.0, "transition_word_rate_per_word": 0.0, "lexical_entropy_bits": 1.584962500721156, "average_word_length_characters": 3.6666666666666665, "key_phrase_rate": 0.0, "key_phrase_rate_description": "The key_phrase_rate is the rate of detected avatar signature key phrases per total word when compared against the ground truth dataset (direct quotes of the avatar), and is the rate of baseline ChatGPT signature key phrases per total word when compared against the baseline ChatGPT dataset."}, "comparison_to_unmodified_llm_response_analysis": {"no_statistically_significantly_difference_from_unmodified_llm_response_using_squared_mahalanobis_distance": false, "unmodified_llm_comparison_isolation_forest_shap_values": {"hdd_lexical_diversity": -0.1408546633695867, "verb_density": -0.17661529729807254, "adjective_density": -0.19007058549066028, "adverb_density": -0.1703055826947579, "pronoun_density": -0.15073443698645472, "interrogative_sentence_ratio": -0.27353189152487084, "dash_rate_per_word": -0.1558936438018881, "question_mark_rate_per_word": -0.3040891934713983, "lexical_entropy_bits": -0.21504872712512824, "average_word_length_characters": -0.13589945649805202}, "unmodified_llm_comparison_isolation_forest_shap_values_description": "Negative values indicate dissimilarity from unmodified llm dataset. Positive values indicate similarity to unmodified llm responses. Scale is -1 to 1.", "no_statistically_significant_difference_between_sample_and_unmodified_llm_according_to_isolation_forest": false}}, "usage": {"prompt_tokens": 21170, "completion_tokens": 9, "total_tokens": 21179, "meter": "messaging_tokens", "tier": "pro", "monthly_allotment": 5000000, "used_to_date": 21179, "remaining": 4978821, "pay_per_use_enabled": false, "usage_period_start": "2026-07-22T14:55:45.330562+00:00", "usage_period_end": "2026-08-22T14:55:45.330562+00:00"}}



