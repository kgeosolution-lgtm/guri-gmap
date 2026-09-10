import { Map, Box, Database, Images } from 'lucide-react';
import type { LayerDefinition } from '@/types/content';
export const layersConfig: LayerDefinition[] = [
  {
    id: '2d',
    title: '2D 지도',
    description: '생활정보를 한눈에 보는 기본지도',
    icon: Map,
    type: 'webmap',
    portalItemId: null,
    mockCount: 148,
  },
  {
    id: '3d',
    title: '3D 구리',
    description: '입체로 만나는 구리의 도시공간',
    icon: Box,
    type: 'scene',
    portalItemId: null,
  },
  {
    id: 'data',
    title: '공간데이터',
    description: '분야별 공간정보 목록과 메타데이터',
    icon: Database,
    type: 'feature',
    portalItemId: null,
    mockCount: 64,
  },
  {
    id: 'aerial',
    title: '항공사진 비교',
    description: '과거와 현재의 도시 변화를 비교',
    icon: Images,
    type: 'imagery',
    portalItemId: null,
  },
];
