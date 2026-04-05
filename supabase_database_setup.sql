-- --------------------------------------------------------
-- Supabase Schema for Twitter Video Downloader
-- --------------------------------------------------------
-- Copy and paste everything in this file into your Supabase SQL Editor and hit "Run"

-- 1. Create Proxies Table (ADVANCED)
CREATE TABLE IF NOT EXISTS public.proxies (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    provider_name TEXT NOT NULL, -- 'OXYLABS' or 'WEBSHARE'
    type TEXT NOT NULL, -- 'rotating' or 'static'
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT,
    password TEXT,
    country TEXT,
    city TEXT,
    assigned_ip TEXT, -- For Oxylabs internal IP tracking
    priority_level INTEGER DEFAULT 2, -- 1 = Highest, 2 = Medium, 3 = Low
    status TEXT DEFAULT 'active', -- 'active', 'inactive', 'banned'
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_response_time FLOAT DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    last_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    UNIQUE(host, port)
);

-- 2. Create Proxy Logs Table
CREATE TABLE IF NOT EXISTS public.proxy_logs (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    proxy_id UUID REFERENCES public.proxies(id) ON DELETE CASCADE,
    provider_name TEXT,
    request_url TEXT,
    status TEXT, -- 'success', 'fail', 'timeout', 'banned'
    response_time FLOAT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Create Proxy Usage Stats Table
CREATE TABLE IF NOT EXISTS public.proxy_usage_stats (
    proxy_id UUID PRIMARY KEY REFERENCES public.proxies(id) ON DELETE CASCADE,
    total_requests INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0,
    ban_rate FLOAT DEFAULT 0,
    last_10_results TEXT[] DEFAULT '{}'::TEXT[],
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);



-- 4. Create Download Logs Table (Keeping existing structure but can be linked to proxies)
CREATE TABLE IF NOT EXISTS public.download_logs (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    twitter_url TEXT NOT NULL,
    proxy_id UUID REFERENCES public.proxies(id) ON DELETE SET NULL,
    status TEXT NOT NULL, -- 'success' or 'failed'
    file_size BIGINT DEFAULT 0,
    processing_time INTEGER DEFAULT 0,
    user_ip TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Create Errors Table
CREATE TABLE IF NOT EXISTS public.errors (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    source TEXT, -- 'worker', 'api', 'proxy_checker', etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Create System Settings Table (For dynamic Admin control)
CREATE TABLE IF NOT EXISTS public.system_settings (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    setting_name TEXT NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Insert Default System Settings
INSERT INTO public.system_settings (setting_name, setting_value) VALUES 
('max_downloads_per_hour', '50'),
('maintenance_mode', 'false'),
('file_expiry', '900')
ON CONFLICT (setting_name) DO NOTHING;

-- 5. Create Security Blocks Table
CREATE TABLE IF NOT EXISTS public.security_blocks (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    block_type TEXT NOT NULL, -- 'ip', 'user_agent'
    block_value TEXT NOT NULL, 
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    UNIQUE(block_type, block_value)
);

-- --------------------------------------------------------
-- Row Level Security (RLS) Policies
-- --------------------------------------------------------
-- Enable RLS on all tables
ALTER TABLE public.proxies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proxy_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proxy_usage_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.download_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.errors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_blocks ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows the anon key (API) to SELECT and INSERT only.
CREATE POLICY "Anon can insert logs" ON public.download_logs FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Anon can insert proxy logs" ON public.proxy_logs FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Anon can read settings" ON public.system_settings FOR SELECT TO anon USING (true);
CREATE POLICY "Anon can read blocks" ON public.security_blocks FOR SELECT TO anon USING (true);
CREATE POLICY "Anon can insert errors" ON public.errors FOR INSERT TO anon WITH CHECK (true);

-- --------------------------------------------------------
-- CMS: Pages, Blog, Media (Page Builder + Landing CMS)
-- Run this section after the above. Uses service_role from your API for writes.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.cms_pages (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.cms_blog_posts (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    featured_image_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.cms_media (
    id UUID DEFAULT extensions.uuid_generate_v4() PRIMARY KEY,
    filename TEXT NOT NULL,
    url TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cms_pages_slug ON public.cms_pages (slug);
CREATE INDEX IF NOT EXISTS idx_cms_pages_status ON public.cms_pages (status);
CREATE INDEX IF NOT EXISTS idx_cms_blog_slug ON public.cms_blog_posts (slug);

ALTER TABLE public.cms_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cms_blog_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cms_media ENABLE ROW LEVEL SECURITY;

-- Public can only read published pages (anon key from your downloader app)
CREATE POLICY "cms_pages_public_read_published"
    ON public.cms_pages FOR SELECT TO anon
    USING (status = 'published');

CREATE POLICY "cms_blog_public_read_published"
    ON public.cms_blog_posts FOR SELECT TO anon
    USING (status = 'published');

-- Optional: allow anon to read media URLs (for public pages embedding images)
CREATE POLICY "cms_media_public_read"
    ON public.cms_media FOR SELECT TO anon
    USING (true);

-- Inserts/updates/deletes: use SUPABASE_SERVICE_ROLE_KEY in FastAPI (bypasses RLS).
-- If you cannot use the service role, uncomment the three policies below for development ONLY:

-- CREATE POLICY "cms_pages_dev_all" ON public.cms_pages FOR ALL TO anon USING (true) WITH CHECK (true);
-- CREATE POLICY "cms_blog_dev_all" ON public.cms_blog_posts FOR ALL TO anon USING (true) WITH CHECK (true);
-- CREATE POLICY "cms_media_dev_all" ON public.cms_media FOR ALL TO anon USING (true) WITH CHECK (true);
