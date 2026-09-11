/** Local dev stays at /; deployment is an opt-in static export. */
const exporting = process.env.GMAP_EXPORT === '1';
export default {
  ...(exporting ? { output: 'export', trailingSlash: true } : {}),
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
};
