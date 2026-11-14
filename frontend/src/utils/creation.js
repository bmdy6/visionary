export const TIERS = { standard: "标准", hd: "高清", master: "大师" };
export const STYLES = {
  default: "默认风格",
  illustration: "治愈插画",
  watercolor: "水彩",
  real: "极致写实",
  product: "商业大片",
  tech_poster: "科技海报",
  travel_guide: "旅游攻略",
  travel: "旅游海报",
  vintage_5s: "复古纪实",
  restore_old: "老照片修复",
  interior: "室内设计",
  product_detail: "详情页设计",
  live_stream: "直播截图",
  ccd_snap: "CCD 随手抓拍",
  eri_silhouette: "轮廓宇宙",
  silk_road: "国风月夜",
  relation_map: "人物关系图谱",
  encyclopedia: "博物馆图鉴",
  knowledge_card: "知识图卡",
  ui_upgrade: "UI 视觉进化",
  app_ui_design: "APP UI 设计",
  campaign_poster: "运营活动页",
};
export const SOURCES = { normal: "网页", assistant: "AI 助手", mcp: "MCP" };
export const active = (job) =>
  ["pending", "generating", "storing"].includes(job.status);
export const errorText = (error, fallback) =>
  typeof error.response?.data?.detail === "string"
    ? error.response.data.detail
    : fallback;
export function continueFrom(job) {
  return {
    prompt: job.prompt,
    quality: job.quality,
    style: job.style,
    aspect_ratio: job.aspect_ratio || "1:1",
    ref_image_url: job.image_url,
  };
}
