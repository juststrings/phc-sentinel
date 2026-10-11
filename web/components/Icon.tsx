// Small inline icon set (no icon-font download, so the app builds and runs offline).
const PATHS: Record<string, string> = {
  mail: "M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm1 2.500V17h16V7.500l-8 5-8-5Zm1.700-.500L12 10.800 18.300 7H5.700Z",
  warning: "M12 3 2 21h20L12 3Zm0 6 6.5 11h-13L12 9Zm-1 3v4h2v-4h-2Zm0 5v2h2v-2h-2Z",
  search: "M10 3a7 7 0 1 0 4.2 12.6l4.6 4.6 1.4-1.4-4.6-4.6A7 7 0 0 0 10 3Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z",
  "eye-off": "M3.3 2 2 3.3l3 3C3.6 7.5 2.5 9.2 2 12c1.3 4.5 5.2 7 10 7 1.8 0 3.4-.4 4.8-1.1l3.9 3.9 1.3-1.3L3.3 2ZM12 17a5 5 0 0 1-4.6-7l1.6 1.6A3 3 0 0 0 12.4 15L14 16.6c-.6.3-1.3.4-2 .4Zm0-12c-1 0-1.900.2-2.800.5l1.700 1.700L12 7a5 5 0 0 1 5 5c0 .4-.1.800-.2 1.200l2.600 2.600C20.800 14.800 21.700 13.500 22 12c-1.300-4.500-5.200-7-10-7Z",
  check: "M12 2 4 5v6c0 5 3.400 9.700 8 11 4.600-1.300 8-6 8-11V5l-8-3Zm-1.500 14.500L7 13l1.400-1.400 2.100 2.100 5.100-5.100L17 10 10.500 16.500Z",
  flag: "M6 3v18h2v-7h9l-1.500-4L17 6H8V3H6Z",
  home: "M12 3 2 12h3v8h5v-6h4v6h5v-8h3L12 3Z",
  list: "M4 6h2v2H4V6Zm4 0h12v2H8V6ZM4 11h2v2H4v-2Zm4 0h12v2H8v-2ZM4 16h2v2H4v-2Zm4 0h12v2H8v-2Z",
  building: "M4 21V5l8-2 8 2v16h-6v-5h-4v5H4Zm4-12v2h2V9H8Zm6 0v2h2V9h-2Z",
  rule: "M4 5h16v2H4V5Zm0 6h10v2H4v-2Zm0 6h16v2H4v-2Zm13-6 1.500 1.500L21.500 9.500 23 11l-4.500 4.500L17 11Z",
  menu: "M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z",
  close: "m6.400 5 5.600 5.600L17.600 5 19 6.400 13.400 12l5.600 5.600-1.400 1.400-5.600-5.600L6.400 19 5 17.600l5.600-5.600L5 6.400 6.400 5Z",
  download: "M11 3h2v9.200l3.300-3.300 1.400 1.400L12 16l-5.700-5.700 1.400-1.400L11 12.200V3ZM5 18h14v2H5v-2Z",
  arrow: "M13 5l7 7-7 7-1.400-1.400L16.200 13H4v-2h12.200l-4.600-4.600L13 5Z",
};

export default function Icon({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} style={{ flexShrink: 0 }}>
      <path d={PATHS[name] ?? PATHS.check} />
    </svg>
  );
}
