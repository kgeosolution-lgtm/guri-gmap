import { ExternalLink, Layers, PawPrint } from 'lucide-react';
import { themeGroups } from '@/config/theme-groups.config';
import { animalUrl, themeUrl } from '@/config/links';

/** 지금 열어볼 수 있는 지도 — 완성된 두 페이지(테마지도, 유기동물 찾기)를 큰 카드로 */
export function MapsNow() {
  const theme = themeUrl('여름');
  const animal = animalUrl();
  return (
    <section id="maps-now" className="krds-section" aria-labelledby="maps-now-title">
      <div className="krds-inner">
        <h2 id="maps-now-title" className="krds-h2">
          지금 열어볼 수 있는 지도
        </h2>
        <p className="krds-desc">완성된 지도 두 가지를 바로 열어보세요. 새 창에서 열려요.</p>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {/* ① 테마지도 */}
          <article className="krds-map-card">
            <a
              href={theme}
              target="_blank"
              rel="noopener"
              className="card-img"
              title="테마지도 (새 창 열림)"
            >
              <img
                src="/images/preview-theme.webp"
                alt="테마지도 화면. 왼쪽 목록과 오른쪽 구리시 지도에 여름 시설이 표시돼 있어요."
                width={1280}
                height={800}
                loading="lazy"
              />
            </a>
            <div className="card-body">
              <h3 className="card-title">
                <span className="ico" aria-hidden="true">
                  <Layers size={22} />
                </span>
                테마지도
              </h3>
              <p className="card-desc">
                무더위쉼터부터 공영주차장까지, 우리 동네 생활 시설을 지도에서 찾아보세요
              </p>
              <div className="krds-tag-wrap medium" aria-label="테마지도 분류">
                {themeGroups.map(({ group }) => (
                  <a
                    key={group}
                    href={themeUrl(group)}
                    className="krds-btn-tag link"
                    target="_blank"
                    rel="noopener"
                    title={`${group} 분류 열기 (새 창 열림)`}
                  >
                    {group}
                  </a>
                ))}
              </div>
              <div className="card-actions">
                <a
                  href={theme}
                  className="krds-btn primary"
                  target="_blank"
                  rel="noopener"
                  title="새 창 열림"
                >
                  테마지도 열기 <ExternalLink className="svg-icon" aria-hidden="true" />
                </a>
              </div>
            </div>
          </article>

          {/* ② 유기동물 찾기 */}
          <article className="krds-map-card">
            <a
              href={animal}
              target="_blank"
              rel="noopener"
              className="card-img"
              title="유기동물 찾기 (새 창 열림)"
            >
              <img
                src="/images/preview-animal.webp"
                alt="유기동물 찾기 화면. 보호 중인 동물 목록과 위치가 지도에 표시돼 있어요."
                width={1280}
                height={800}
                loading="lazy"
              />
            </a>
            <div className="card-body">
              <h3 className="card-title">
                <span className="ico" aria-hidden="true">
                  <PawPrint size={22} />
                </span>
                유기동물 찾기
              </h3>
              <p className="card-desc">보호 중인 아이들을 지도에서 찾아보세요</p>
              <div className="card-actions">
                <a
                  href={animal}
                  className="krds-btn primary"
                  target="_blank"
                  rel="noopener"
                  title="새 창 열림"
                >
                  유기동물 찾기 열기 <ExternalLink className="svg-icon" aria-hidden="true" />
                </a>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
