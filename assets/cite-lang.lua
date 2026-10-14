--[[
cite-lang – per-item punctuation for mixed-language author-date citations
(thesisbug2, MIT). Runs after citeproc (after multibib.lua in `filters:`).

《遠景基金會季刊》撰稿規範 (113.10.30) writes a Chinese-source citation with
full-width punctuation —（陳欣之，2010，25-40）、（蔡佳泓、俞振華，2011，74）、
（黃秀端等人，2020，37）— and a Western-source citation with half-width
punctuation — (Allison, 2020, 94), (Stoker & Marsh, 2007, 1-18),
(Walentek et al., 2001, 417-418). CSL cannot vary punctuation by the cited
item's language, so the style (apa-zh-TW.csl) renders every citation the
Chinese way and this filter rewrites the items whose author is Latin-script.
A citation group's outer parentheses and separators follow its first item;
each item's inner punctuation follows that item. Multi-byte characters are
handled with plain finds, never character classes, which are byte-wise in Lua.
]]

local function is_latin_first(s)
  -- The first alphabetic character of the item decides its language.
  for _, cp in utf8.codes(s) do
    if (cp >= 0x4E00 and cp <= 0x9FFF) or (cp >= 0x3400 and cp <= 0x4DBF)
       or (cp >= 0xF900 and cp <= 0xFAFF) then
      return false
    end
    if (cp >= 65 and cp <= 90) or (cp >= 97 and cp <= 122) then
      return true
    end
  end
  return false
end

local function replace_all(s, from, to)
  local out, i = {}, 1
  while true do
    local a, b = s:find(from, i, true)
    if not a then out[#out + 1] = s:sub(i); break end
    out[#out + 1] = s:sub(i, a - 1)
    out[#out + 1] = to
    i = b + 1
  end
  return table.concat(out)
end

local function to_western(item)
  item = replace_all(item, "，", ", ")
  item = replace_all(item, "、", " & ")
  item = replace_all(item, "等人", " et al.")
  item = replace_all(item, "未註明", "n.d.")
  item = replace_all(item, "（", " (")
  item = replace_all(item, "）", ")")
  item = item:gsub("  +", " "):gsub("^%s+", ""):gsub("%s+$", "")
  item = item:gsub("%s+,", ",")
  return item
end

local function split_items(body)
  -- split on the full-width or half-width semicolon citeproc uses between items
  local items, i = {}, 1
  while true do
    local a, b = body:find("；", i, true)
    local a2, b2 = body:find("; ", i, true)
    if a2 and (not a or a2 < a) then a, b = a2, b2 end
    if not a then items[#items + 1] = body:sub(i); break end
    items[#items + 1] = body:sub(i, a - 1)
    i = b + 1
  end
  return items
end

local function starts(s, p) return s:sub(1, #p) == p end
local function ends(s, p) return #p <= #s and s:sub(-#p) == p end

local function rewrite(text)
  local t = text:gsub("^%s+", ""):gsub("%s+$", "")
  local lead, trail = text:match("^(%s*)"), text:match("(%s*)$")
  local opened = (starts(t, "（") and "（") or (starts(t, "(") and "(") or nil
  local closed = (ends(t, "）") and "）") or (ends(t, ")") and ")") or nil
  if opened and closed then
    local body = t:sub(#opened + 1, #t - #closed)
    local items = split_items(body)
    if #items == 0 then return text end
    local first_latin = is_latin_first(items[1])
    for k, it in ipairs(items) do
      it = it:gsub("^%s+", ""):gsub("%s+$", "")
      items[k] = is_latin_first(it) and to_western(it) or replace_all(it, " 等人", "等人")
    end
    local sep = first_latin and "; " or "；"
    local l, r = (first_latin and "(" or "（"), (first_latin and ")" or "）")
    return lead .. l .. table.concat(items, sep) .. r .. trail
  end
  -- author-in-text form: 「陳欣之（2010，60）」 / 「Jervis （1999，50）」
  local a = t:find("（", 1, true) or t:find("(", 1, true)
  if not a or a == 1 then return text end
  local pre, inner = t:sub(1, a - 1), t:sub(a)
  if not is_latin_first(pre) then
    -- Chinese author in text: 「陳欣之（2010，60）」 — no space before the parenthesis
    return lead .. pre:gsub("%s+$", "") .. replace_all(inner, " 等人", "等人") .. trail
  end
  pre = pre:gsub("%s+$", "")
  return lead .. pre .. " " .. to_western(inner):gsub("^%s+", "") .. trail
end

local function inlines_from(text)
  local out = pandoc.List()
  if text:match("^%s") then out:insert(pandoc.Space()) end
  local first = true
  for word in text:gmatch("%S+") do
    if not first then out:insert(pandoc.Space()) end
    out:insert(pandoc.Str(word))
    first = false
  end
  if text:match("%s$") then out:insert(pandoc.Space()) end
  return out
end

return {
  {
    Cite = function (c)
      local text = pandoc.utils.stringify(c.content)
      local new = rewrite(text)
      if new == text then return nil end
      c.content = inlines_from(new)
      return c
    end
  }
}
