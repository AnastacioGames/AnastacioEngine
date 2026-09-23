// Rain Shader
// Copyright © OSAMA MSA. All Rights Reserved.
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D bgl_DataTextures[1];
uniform float timer;
const vec3 LIGHT_DIRECTION = vec3(0.0, 0.0, 1.0);
in vec2 texcoord;

const float RIPPLE_SCALE      = 6.0;
const float RIPPLE_SPEED      = 2.0;
const float RIPPLE_THICKNESS  = 0.02;
const float RIPPLE_SMOOTHNESS = 0.07;
const float RIPPLE_INTENSITY  = 0.03;

const float RAIN_SPEED        = 100000.0;
const float RAIN_INTENSITY    = 0.35;
const vec3  RAIN_COLOR        = vec3(0.85, 0.92, 1.0);

const float RAIN_DENSITY      = 90.;
const float RAIN_LENGTH       = 1.0;
const float RAIN_THICKNESS    = 0.05;
const float RAIN_GLOW         = 0.1;

vec3 createHash(vec3 position) {
    return fract(
        sin(vec3(
            dot(position, vec3(1.0, 57.0, 113.0)),
            dot(position, vec3(57.0, 113.0, 1.0)),
            dot(position, vec3(113.0, 1.0, 57.0))))
        * 43758.5453);
}

float getRainRipples3D(vec3 coord) {
    vec3 i = floor(coord);
    vec3 f = fract(coord);
    float rippleEffect = 0.0;

    for (int z = -1; z <= 1; z++) {
        for (int y = -1; y <= 1; y++) {
            for (int x = -1; x <= 1; x++) {
                vec3 neighbor = vec3(float(x), float(y), float(z));
                vec3 randomVector = createHash(i + neighbor);
                vec3 difference = neighbor - f + randomVector;
                
                float distance = length(difference);
                float dropTime = fract(timer * RIPPLE_SPEED + randomVector.x);

                float distToRing1 = abs(distance - dropTime);
                float distToRing2 = abs(distance - dropTime + 0.12);

                float ring1 = smoothstep(RIPPLE_THICKNESS + RIPPLE_SMOOTHNESS, max(0.0, RIPPLE_THICKNESS - RIPPLE_SMOOTHNESS), distToRing1);
                float ring2 = smoothstep(RIPPLE_THICKNESS + RIPPLE_SMOOTHNESS, max(0.0, RIPPLE_THICKNESS - RIPPLE_SMOOTHNESS), distToRing2);

                float fade = 1.0 - smoothstep(0.3, 0.95, dropTime);
                float totalRing = (ring1 + ring2 * 0.4) * fade;

                rippleEffect = max(rippleEffect, totalRing);
            }
        }
    }
    return rippleEffect;
}

float getSingleRainLayer(vec3 p, float layerScale, float speedModifier, float seed) {
    vec3 p_scaled = p * layerScale * (RAIN_DENSITY * 0.05);
    p_scaled.z /= max(0.1, RAIN_LENGTH);
    p_scaled.z += timer * RAIN_SPEED * speedModifier * 0.005;
    
    vec3 cell = floor(p_scaled);
    vec3 f = fract(p_scaled);
    vec3 h = createHash(cell + seed);
    
    vec2 center = h.xy * 0.8 + 0.1;
    float horizontalDist = length(f.xy - center);
    
    float streak = smoothstep(RAIN_THICKNESS + RAIN_GLOW, max(0.0, RAIN_THICKNESS - RAIN_GLOW), horizontalDist);
    float verticalMask = smoothstep(0.0, 0.15, f.z) * smoothstep(1.0, 0.5, f.z);
    
    return streak * verticalMask * h.z;
}

vec3 getWorldPositionFromDepth(vec2 uv) {
    float depthValue = texture(bgl_DepthTexture, uv).x;
    
    // Rain Shader
    // Copyright © OSAMA MSA. All Rights Reserved.
    vec3 ndc_position = vec3(uv * 2.0 - 1.0, depthValue * 2.0 - 1.0);

    vec4 viewSpacePosition = gl_ProjectionMatrixInverse * vec4(ndc_position, 1.0);
    viewSpacePosition /= viewSpacePosition.w; // القسمة المنظورية الصحيحة

    vec4 worldSpacePosition = gl_ModelViewMatrixInverse * viewSpacePosition;
    
    // إرجاع الإحداثيات دون القسمة الإضافية الخاطئة على w التي كانت موجودة سابقاً
    return worldSpacePosition.xyz;
}

void main() {
    vec2 uv = gl_TexCoord[0].st;
    vec3 normal = texture(bgl_DataTextures[0], uv).rgb;
    vec3 transformedNormal = normalize(inverse(gl_NormalMatrix) * normal);

    vec3 camPos = (gl_ModelViewMatrixInverse * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    vec3 worldPos = getWorldPositionFromDepth(uv);
    
    vec3 viewDir = normalize(worldPos - camPos);
    float sceneDepth = length(worldPos - camPos);

    vec3 rippleWorldPos = worldPos * RIPPLE_SCALE; 
    float rippleNoise = getRainRipples3D(rippleWorldPos);
    
    float depth = texture(bgl_DepthTexture, uv).x;
    float isNotBackground = 1.0 - (step(0.999, depth) + step(1.001, depth) * 0.0);
    float luminosity = max(0.0, dot(transformedNormal, -LIGHT_DIRECTION));
    
    vec3 originalColor = texture(bgl_RenderedTexture, uv).rgb;
    vec3 finalColor = mix(originalColor, originalColor + vec3(luminosity * RIPPLE_INTENSITY), rippleNoise * isNotBackground);
    
    float rainVisibility = 0.0;
    
    if (sceneDepth > 1.5) {
        rainVisibility += getSingleRainLayer(camPos + viewDir * 1.5, 0.6, 1.2, 12.34) * 0.1;
    }
    if (sceneDepth > 4.0) {
        rainVisibility += getSingleRainLayer(camPos + viewDir * 4.0, 1.2, 1.0, 56.78) * 0.3;
    }
    if (sceneDepth > 10.0) {
        rainVisibility += getSingleRainLayer(camPos + viewDir * 10.0, 2.2, 0.8, 91.01) * 0.8;
    }
    
    finalColor += RAIN_COLOR * rainVisibility * RAIN_INTENSITY;
    
    gl_FragColor = vec4(finalColor, 1.0);
}