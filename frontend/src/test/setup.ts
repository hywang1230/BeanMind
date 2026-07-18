import { config } from '@vue/test-utils'

config.global.stubs.VanNavBar = {
  props: {
    title: String,
    leftArrow: Boolean,
    leftText: String,
    rightText: String,
  },
  emits: ['clickLeft', 'clickRight'],
  template: `
    <div class="van-nav-bar">
      <button
        v-if="leftArrow || leftText || $slots.left"
        type="button"
        class="van-nav-bar__left"
        @click="$emit('clickLeft')"
      >
        {{ leftText }}<slot name="left" />
      </button>
      <span class="van-nav-bar__title">{{ title }}</span>
      <div
        v-if="rightText || $slots.right"
        class="van-nav-bar__right"
        @click="$emit('clickRight')"
      >
        {{ rightText }}<slot name="right" />
      </div>
    </div>
  `,
}
