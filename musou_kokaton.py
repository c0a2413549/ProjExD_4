import math
import os
import random
import sys
import time
import pygame as pg


WIDTH = 1100  # ゲームウィンドウの幅
HEIGHT = 650  # ゲームウィンドウの高さ
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def check_bound(obj_rct: pg.Rect) -> tuple[bool, bool]:
    """
    オブジェクトが画面内or画面外を判定し，真理値タプルを返す関数
    引数：こうかとんや爆弾，ビームなどのRect
    戻り値：横方向，縦方向のはみ出し判定結果（画面内：True／画面外：False）
    """
    yoko, tate = True, True
    if obj_rct.left < 0 or WIDTH < obj_rct.right:
        yoko = False
    if obj_rct.top < 0 or HEIGHT < obj_rct.bottom:
        tate = False
    return yoko, tate


def calc_orientation(org: pg.Rect, dst: pg.Rect) -> tuple[float, float]:
    """
    orgから見て，dstがどこにあるかを計算し，方向ベクトルをタプルで返す
    引数1 org：爆弾SurfaceのRect
    引数2 dst：こうかとんSurfaceのRect
    戻り値：orgから見たdstの方向ベクトルを表すタプル
    """
    x_diff, y_diff = dst.centerx - org.centerx, dst.centery - org.centery
    norm = math.sqrt(x_diff**2 + y_diff**2)
    if norm == 0:
        return 0.0, 0.0
    return x_diff / norm, y_diff / norm


class Bird(pg.sprite.Sprite):
    """
    ゲームキャラクター（こうかとん）に関するクラス
    """
    delta = {  # 押下キーと移動量の辞書
        pg.K_UP: (0, -1),
        pg.K_DOWN: (0, +1),
        pg.K_LEFT: (-1, 0),
        pg.K_RIGHT: (+1, 0),
    }

    def __init__(self, num: int, xy: tuple[int, int]):
        """
        こうかとん画像Surfaceを生成する
        引数1 num：こうかとん画像ファイル名の番号
        引数2 xy：こうかとん画像の位置座標タプル
        """
        super().__init__()
        img0 = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 0.9)
        img = pg.transform.flip(img0, True, False)  # デフォルトのこうかとん
        self.imgs = {
            (+1, 0): img,  # 右
            (+1, -1): pg.transform.rotozoom(img, 45, 0.9),  # 右上
            (0, -1): pg.transform.rotozoom(img, 90, 0.9),  # 上
            (-1, -1): pg.transform.rotozoom(img0, -45, 0.9),  # 左上
            (-1, 0): img0,  # 左
            (-1, +1): pg.transform.rotozoom(img0, 45, 0.9),  # 左下
            (0, +1): pg.transform.rotozoom(img, -90, 0.9),  # 下
            (+1, +1): pg.transform.rotozoom(img, -45, 0.9),  # 右下
        }
        self.dire = (+1, 0)
        self.image = self.imgs[self.dire]
        self.rect = self.image.get_rect()
        self.rect.center = xy
        self.speed = 10

        # --- 追加状態 ---
        self.state = "normal"   # "normal" または "hyper"
        self.hyper_life = 0     # 無敵状態の残りフレーム
        # ----------------

    def change_img(self, num: int, screen: pg.Surface):
        """
        こうかとん画像を切り替え，画面に転送する
        引数1 num：こうかとん画像ファイル名の番号
        引数2 screen：画面Surface
        """
        self.image = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 0.9)
        screen.blit(self.image, self.rect)

    def update(self, key_lst: list[bool], screen: pg.Surface):
        """
        押下キーに応じてこうかとんを移動させる
        無敵状態中は画像を変換して表示し、残り時間を減らす
        引数1 key_lst：押下キーの真理値リスト
        引数2 screen：画面Surface
        """
        sum_mv = [0, 0]
        for k, mv in __class__.delta.items():
            if key_lst[k]:
                sum_mv[0] += mv[0]
                sum_mv[1] += mv[1]
        
        # LSHIFTキーが押されている間はスピードアップ
        if key_lst[pg.K_LSHIFT]:
            self.speed = 20
        else:
            self.speed = 10  # 押されていない時は元のスピードに

        self.rect.move_ip(self.speed * sum_mv[0], self.speed * sum_mv[1])
        if check_bound(self.rect) != (True, True):
            self.rect.move_ip(-self.speed * sum_mv[0], -self.speed * sum_mv[1])
        if not (sum_mv[0] == 0 and sum_mv[1] == 0):
            # 正規化されていない方向ベクトル（整数）でimgsを参照
            self.dire = tuple(sum_mv)
            # imgsに用意されている方向が8方向整数のみのため、
            # もし該当キーが無ければ向きを基本(+1,0)にする
            if self.dire in self.imgs:
                base_img = self.imgs[self.dire]
            else:
                base_img = self.imgs[(+1, 0)]
            # 普通時は素の画像をセット（ただし無敵時は変換して表示する）
            if self.state != "hyper":
                self.image = base_img
        else:
            # 押下なしのときは現在の向き画像を維持（無敵時は下で処理）
            base_img = self.imgs.get(self.dire, self.imgs[(+1, 0)])
            if self.state != "hyper":
                self.image = base_img

        # 無敵状態中の処理：画像変換＆持続時間のカウントダウン
        if self.state == "hyper":
            # 常に向きに応じた元画像を基に変換する（累積変換を避けるため）
            base_img = self.imgs.get(self.dire, self.imgs[(+1, 0)])
            try:
                # 指定どおりlaplacian変換（環境によっては存在しない場合があるが指示に従う）
                hyper_img = pg.transform.laplacian(base_img)
            except Exception:
                # 環境によっては laplacian が無い/失敗するので、代替として反転を使う（警告は出さない）
                hyper_img = pg.transform.flip(base_img, True, True)
            self.image = hyper_img
            self.hyper_life -= 1
            if self.hyper_life < 0:
                self.state = "normal"
                # 無敵解除時は向きに応じた通常画像に戻す
                self.image = self.imgs.get(self.dire, self.imgs[(+1, 0)])

        screen.blit(self.image, self.rect)


class Bomb(pg.sprite.Sprite):
    """
    爆弾に関するクラス
    """
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]

    def __init__(self, emy: "Enemy", bird: Bird):
        """
        爆弾円Surfaceを生成する
        引数1 emy：爆弾を投下する敵機
        引数2 bird：攻撃対象のこうかとん
        """
        super().__init__()
        rad = random.randint(10, 50)  # 爆弾円の半径：10以上50以下の乱数
        self.image = pg.Surface((2 * rad, 2 * rad))
        color = random.choice(__class__.colors)  # 爆弾円の色：クラス変数からランダム選択
        pg.draw.circle(self.image, color, (rad, rad), rad)
        self.image.set_colorkey((0, 0, 0))
        self.rect = self.image.get_rect()
        # 爆弾を投下するemyから見た攻撃対象のbirdの方向を計算
        self.vx, self.vy = calc_orientation(emy.rect, bird.rect)
        self.rect.centerx = emy.rect.centerx
        self.rect.centery = emy.rect.centery + emy.rect.height // 2
        self.speed = 6
        self.state = "active"

    def update(self):
        """
        爆弾を速度ベクトルself.vx, self.vyに基づき移動させる
        引数 screen：画面Surface
        """
        self.rect.move_ip(self.speed * self.vx, self.speed * self.vy)
        if check_bound(self.rect) != (True, True):
            self.kill()


class Beam(pg.sprite.Sprite):
    """
    ビームに関するクラス
    """
    def __init__(self, bird: Bird, angle0=0):  #angle0をデフォルトの値0で追加
        """
        ビーム画像Surfaceを生成する
        引数 bird：ビームを放つこうかとん
        """
        super().__init__()
        self.vx, self.vy = bird.dire

        angle = math.degrees(math.atan2(-self.vy, self.vx)) + angle0  #angle0をビームの回転角度に加算
        self.image = pg.transform.rotozoom(pg.image.load(f"fig/beam.png"), angle, 1.0)
        self.vx = math.cos(math.radians(angle))
        self.vy = -math.sin(math.radians(angle))
        self.rect = self.image.get_rect()
        self.rect.centery = bird.rect.centery + bird.rect.height * self.vy
        self.rect.centerx = bird.rect.centerx + bird.rect.width * self.vx
        self.speed = 10

    def update(self):
        """
        ビームを速度ベクトルself.vx, self.vyに基づき移動させる
        引数 screen：画面Surface
        """
        self.rect.move_ip(self.speed * self.vx, self.speed * self.vy)
        if check_bound(self.rect) != (True, True):
            self.kill()


class NeoBeam(pg.sprite.Sprite):  #新たにNeoBeamクラスを追加
    """
    複数のビームを出すためのクラス
    """
    def __init__(self, bird: Bird, num: int):  #イニシャライザの引数をこうかとんbirdとビーム数numに
        self.bird=bird
        self.num=num  #ここの数字でビームの数を決定
    
    def gen_beams(self) -> list[Beam]:
        """
        numに応じて角度を計算し、Beamのリストを返す
        """
        beams = []
        if self.num <= 0:
            return beams
        
        # numが1の場合は角度0のビームを1本生成
        if self.num == 1:
            beams.append(Beam(self.bird))
            return beams
            
        # num > 1 の場合：角度の範囲num-1で割ってステップを求める
        step = 100 / (self.num - 1)
        
        for i in range(self.num):
            # i = 0 のとき -50, i = num-1 のとき +50 となるように angle0 を計算
            angle0 = -50 + step * i
            beams.append(Beam(self.bird, angle0))
            
        return beams


class Explosion(pg.sprite.Sprite):
    """
    爆発に関するクラス
    """
    def __init__(self, obj: "Bomb|Enemy", life: int):
        """
        爆弾が爆発するエフェクトを生成する
        引数1 obj：爆発するBombまたは敵機インスタンス
        引数2 life：爆発時間
        """
        super().__init__()
        img = pg.image.load(f"fig/explosion.gif")
        self.imgs = [img, pg.transform.flip(img, 1, 1)]
        self.image = self.imgs[0]
        self.rect = self.image.get_rect(center=obj.rect.center)
        self.life = life

    def update(self):
        """
        爆発時間を1減算した爆発経過時間_lifeに応じて爆発画像を切り替えることで
        爆発エフェクトを表現する
        """
        self.life -= 1
        # lifeが0以下でも index参照しないように保護
        if self.life >= 0:
            self.image = self.imgs[self.life // 10 % 2]
        if self.life < 0:
            self.kill()


class Enemy(pg.sprite.Sprite):
    """
    敵機に関するクラス
    """
    imgs = [pg.image.load(f"fig/alien{i}.png") for i in range(1, 4)]

    def __init__(self):
        super().__init__()
        self.image = pg.transform.rotozoom(random.choice(__class__.imgs), 0, 0.8)
        self.rect = self.image.get_rect()
        self.rect.center = random.randint(0, WIDTH), 0
        self.vx, self.vy = 0, +6
        self.bound = random.randint(50, HEIGHT // 2)  # 停止位置
        self.state = "down"  # 降下状態or停止状態
        self.interval = random.randint(50, 300)  # 爆弾投下インターバル

    def update(self):
        """
        敵機を速度ベクトルself.vyに基づき移動（降下）させる
        ランダムに決めた停止位置_boundまで降下したら，_stateを停止状態に変更する
        引数 screen：画面Surface
        """
        if self.rect.centery > self.bound:
            self.vy = 0
            self.state = "stop"
        self.rect.move_ip(self.vx, self.vy)


class Score:
    """
    打ち落とした爆弾，敵機の数をスコアとして表示するクラス
    爆弾：1点
    敵機：10点
    """
    def __init__(self):
        self.font = pg.font.Font(None, 50)
        self.color = (0, 0, 255)
        self.value = 1000
        self.image = self.font.render(f"Score: {self.value}", 0, self.color)
        self.rect = self.image.get_rect()
        self.rect.center = 100, HEIGHT - 50

    def update(self, screen: pg.Surface):
        self.image = self.font.render(f"Score: {self.value}", 0, self.color)
        screen.blit(self.image, self.rect)

class Gravity(pg.sprite.Sprite):
    """
    重力場を表示させるクラス
    消費スコア：２００
    """

    def __init__(self, life):
        """
        引数 life :発動時間
        """
        super().__init__()
        self.life = life
        self.image = pg.Surface((WIDTH, HEIGHT))
        self.rect = self.image.get_rect()
        pg.draw.rect(self.image,(0, 0, 0), (0, 0, WIDTH, HEIGHT))
        self.image.set_alpha(128)

    def update(self):
        self.life -= 1
        if(self.life < 0):
            self.kill()

class EMP(pg.sprite.Sprite):

    def __init__(self,emys,bombs,screen):
        super().__init__()
        self.image = pg.Surface((1, 1), pg.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(0, 0))
        self.emys = emys
        self.bombs = bombs
        self.screen = screen
        self.life = 3

        for emy in self.emys:
            emy.interval = math.inf
            emy.image = pg.transform.laplacian(emy.image)

        for bomb in self.bombs:
            bomb.speed /= 2
            bomb.state = "inactive"

        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((255, 255, 0, 128))  # 半透明黄色
        self.screen.blit(overlay, (0, 0))
        pg.display.update()
        pg.time.delay(int(0.05 * 1000))

    def update(self):
        self.life -= 1
        if self.life <= 0:
            self.kill()


class Shield(pg.sprite.Sprite):
    """
    防御壁に関するクラス
    """
    def __init__(self, bird: Bird, life: int = 400):
        super().__init__()
        self.bird = bird
        self.life = life
        self.base_image = pg.Surface((20, bird.rect.height * 2))
        self.base_image.fill((0, 0, 0)) 
        pg.draw.rect(self.base_image, (0, 0, 255), (0, 0, 20, bird.rect.height * 2))
        self.base_image.set_colorkey((0, 0, 0))  
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=bird.rect.center)

    def update(self):
        self.life -= 1
        if self.life <= 0:
            self.kill()
            return
        vx, vy = self.bird.dire
        angle = math.degrees(math.atan2(-vy, vx))
        rotated_image = pg.transform.rotozoom(self.base_image, angle, 1.0)
        rotated_image.set_colorkey((0, 0, 0))
        self.image = rotated_image
        offset_x = self.bird.rect.width * vx
        offset_y = self.bird.rect.height * vy
        self.rect = rotated_image.get_rect(center=(self.bird.rect.centerx + offset_x,self.bird.rect.centery + offset_y))


def main():
    pg.display.set_caption("真！こうかとん無双")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    bg_img = pg.image.load(f"fig/pg_bg.jpg")
    score = Score()

    bird = Bird(3, (900, 400))
    bombs = pg.sprite.Group()
    beams = pg.sprite.Group()
    exps = pg.sprite.Group()
    emys = pg.sprite.Group()
    gravity = pg.sprite.Group()
    emps = pg.sprite.Group()
    shield = pg.sprite.Group()

    tmr = 0
    clock = pg.time.Clock()
    while True:
        key_lst = pg.key.get_pressed()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 0
            
            if event.type == pg.KEYDOWN:
                # K_SPACE: ビーム発射 (LSHIFT同時押しでNeoBeam)
                if event.key == pg.K_SPACE:
                    if key_lst[pg.K_LSHIFT]:
                        # 弾幕発射 (num=5)
                        neo_beam = NeoBeam(bird, 5)
                        beams.add(neo_beam.gen_beams()) # 複数のビームをリストで追加
                    else:
                        beams.add(Beam(bird))
                
                # K_s: シールド発動
                if event.key == pg.K_s and score.value >= 50 and len(shield) == 0:
                    # 防御壁発動条件：スコア50以上＆壁が存在しない
                    shield.add(Shield(bird))
                    score.value -= 50
                
                # K_RETURN: 重力場発動
                if event.key == pg.K_RETURN:
                    if score.value > 200:
                        score.value -= 200
                        gra = Gravity(400)
                        gravity.add(gra)

                # K_e: EMP発動
                if event.key == pg.K_e:
                    if score.value > 20 and len(emps) ==0:
                        score.value -=20
                        emps.add(EMP(emys,bombs,screen))

        # --- 発動条件チェック（右Shift押下 & score > 100） ---
        # (KEYDOWNイベントではなく、押下状態 key_lst で判定)
        # 発動時はスコアを100消費し、state="hyper", hyper_life=500 にする
        if key_lst[pg.K_RSHIFT] and score.value > 100 and bird.state != "hyper":
            bird.state = "hyper"
            bird.hyper_life = 500
            score.value -= 100
            
        screen.blit(bg_img, [0, 0])

        if tmr % 200 == 0:  # 200フレームに1回，敵機を出現させる
            emys.add(Enemy())

        for emy in emys:
            if emy.state == "stop" and tmr % emy.interval == 0:
                # 敵機が停止状態に入ったら，intervalに応じて爆弾投下
                bombs.add(Bomb(emy, bird))

        for emy in pg.sprite.groupcollide(emys, beams, True, True).keys():  # ビームと衝突した敵機リスト
            exps.add(Explosion(emy, 100))  # 爆発エフェクト
            score.value += 10  # 10点アップ
            bird.change_img(6, screen)  # こうかとん喜びエフェクト

        for bomb in pg.sprite.groupcollide(bombs, beams, True, True).keys():  # ビームと衝突した爆弾リスト
            if bomb.state == "active":
                exps.add(Explosion(bomb, 50))  # 爆発エフェクト
                score.value += 1  # 1点アップ

        pg.sprite.groupcollide(bombs, shield, True, False)

        # こうかとんと爆弾の衝突判定（無敵時はゲームオーバーにならない）
        collided_bombs = pg.sprite.spritecollide(bird, bombs, True)
        if collided_bombs:
            # 複数衝突を考慮してループ
            for bomb in collided_bombs:
                if bird.state == "hyper":
                    # 無敵時：爆弾を爆発させ、スコア+1、ゲーム継続
                    exps.add(Explosion(bomb, 50))
                    score.value += 1
                else:
                    # 通常時：ゲームオーバー処理（元の挙動）
                    if bomb.state == "active":
                        bird.change_img(8, screen)  # こうかとん悲しみエフェクト
                        score.update(screen)
                        pg.display.update()
                        time.sleep(2)
                        return
        
        for emy in pg.sprite.groupcollide(emys, gravity, True, False).keys():  # ビームと衝突した重力場リスト
            exps.add(Explosion(emy, 100))  # 爆発エフェクト
            score.value += 10  # 10点アップ
            bird.change_img(6, screen)  # こうかとん喜びエフェクト

        for bomb in pg.sprite.groupcollide(bombs, gravity, True, False).keys():  # ビームと衝突した重力場リスト
            exps.add(Explosion(bomb, 50))  # 爆発エフェクト
            score.value += 1  # 1点アップ
            

        bird.update(key_lst, screen)
        beams.update()
        beams.draw(screen)
        emys.update()
        emys.draw(screen)
        bombs.update()
        bombs.draw(screen)
        exps.update()
        exps.draw(screen)
        score.update(screen)
        gravity.update()
        gravity.draw(screen)
        emps.update()
        emps.draw(screen)
        shield.draw(screen)
        shield.update()
        pg.display.update()
        tmr += 1
        clock.tick(50)


if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()
    sys.exit()